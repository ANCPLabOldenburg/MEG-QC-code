# Main script calling all other functions. 
# Will add imports here when other functions are done and moved from notebooks into py files

# For now it s wrapped into a function to be called in RMSE and Freq spectrum. When all done function will be removed

import configparser

config = configparser.ConfigParser()
config.read('settings.ini')
sids = config['DEFAULT']['sid']
sid_list = list(sids.split(","))


#def initial_stuff(duration: int or None, config: dict):
def initial_stuff(sid):


    '''Here all the initial actions need to work with MEG data are done: 
    - load fif file and convert into raw,
    - create folders in BIDS compliant format,
    - crop the data if needed,
    - filter and downsample the data,
    - epoch the data.

    Args:
    duration (int): how long the cropped data should be, in seconds

    Returns: 
    n_events (int): number of events(=number of epochs)
    df_epochs_mags (pd. Dataframe): data frame containing data for all epochs for mags 
    df_epochs_grads (pd. Dataframe): data frame containing data for all epochs for grads 
    epochs_mags (mne. Epochs): epochs as mne data structure for magnetometers
    epochs_grads (mne. Epochs): epochs as mne data structure for gradiometers 
    mags (list of tuples): magnetometer channel name + its index
    grads (list of tuples): gradiometer channel name + its index
    raw_bandpass(mne.raw): data only filtered, cropped (*)
    raw_bandpass_resamp(mne.raw): data filtered and resampled, cropped (*)
    raw_cropped(mne.io.Raw): data in raw format, cropped, not filtered, not resampled (*)
    raw(mne.io.Raw): original data in raw format, not cropped, not filtered, not resampled.
    (*): if duration was set to None - the data will not be cropped and these outputs 
    will return what is stated, but in origibal duration.

    Yes, these are a lot  of data output option, we can reduce them later when we know what will not be used.
    '''

    config = configparser.ConfigParser()
    config.read('settings.ini')

    #config.sections()
    #config['DEFAULT']['data_file']

    default_section = config['DEFAULT']
    data_file = default_section['data_file']
    duration = default_section.getint('duration') #int(config['DEFAULT']['duration'])
    #sid = default_section['sid']

    from data_load_and_folders import load_meg_data, make_folders_meg, filter_and_resample_data, Epoch_meg

    #Load data
    #data_file = '../data/sub_HT05ND16/210811/mikado-1.fif/'
    #data_file = config['DEFAULT']['data_file']

    raw, mags, grads=load_meg_data(data_file)

    #Create folders:
    make_folders_meg(sid)

    #crop the data to calculate faster
    raw_cropped = raw.copy()
    if duration is not None:
        raw_cropped.crop(0, duration) 

    #apply filtering and downsampling:

    filtering_section = config['Filter_and_resample']
    l_freq = filtering_section.getfloat('l_freq') 
    h_freq = filtering_section.getfloat('h_freq') 
    method = filtering_section['method']
    raw_bandpass, raw_bandpass_resamp=filter_and_resample_data(data=raw_cropped,l_freq=l_freq, h_freq=h_freq, method=method)

    #Apply epoching: USE NON RESAMPLED DATA. Or should we resample after epoching? 
    # Since sampling freq is 1kHz and resampling is 500Hz, it s not that much of a win...

    epoching_section = config['Epoching']
    stim_channel = default_section['stim_channel'] #DO WE ALWAYS HAVE A STIM CHANNEL?
    event_dur = epoching_section.getfloat('event_dur') 
    epoch_tmin = epoching_section.getfloat('epoch_tmin') 
    epoch_tmax = epoching_section.getfloat('epoch_tmax') 

    n_events, df_epochs_mags, df_epochs_grads, epochs_mags, epochs_grads=Epoch_meg(data=raw_bandpass, 
        stim_channel=stim_channel, event_dur=event_dur, epoch_tmin=epoch_tmin, epoch_tmax=epoch_tmax)

    return n_events, df_epochs_mags, df_epochs_grads, epochs_mags, epochs_grads, mags, grads, raw_bandpass, raw_bandpass_resamp, raw_cropped, raw


def selected_channel_types(section: configparser.SectionProxy):
    """get do_for selection for given config"""

    do_for = section['do_for']

    if do_for == 'none':
        return
    elif do_for == 'mags':
        return ['mags']
    elif do_for == 'grads':
        return ['grads']
    elif do_for == 'both':
        return ['mags', 'grads']

def MEG_QC_rmse(sid, channels, df_epochs, channel_names, filtered_d_resamp, n_events):

    from universal_plots import boxplot_channel_epoch_hovering_plotly
    from universal_html_report import make_RMSE_html_report

    rmse_section = config['RMSE']

    # parse from config the channel types that RMSE has to be done for (mags, grads, both or none - as given in do_for in RMSE section)
    channel_types = selected_channel_types(rmse_section)

    if channel_types is None:
        return

    # import RMSE_meg_qc as rmse #or smth like this - when it's extracted to .py
    std_lvl = rmse_section.getint('std_lvl')

    list_of_figure_paths = []
    list_of_figure_paths_std_epoch = []
    big_std_with_value = {}
    small_std_with_value = {}
    fig = {}
    fig_path = {}
    df_std = {}
    fig_std_epoch = {}
    fig_path_std_epoch = {}
    rmse = {}

    # will run for both if mags and grads both chosen,otherwise just for one of them:
    for channel_type in channel_types:
        big_std_with_value[channel_type], small_std_with_value[channel_type], rmse[channel_type] = RMSE_meg_all(data=filtered_d_resamp, channels=channels[channel_type], std_lvl=1)

        fig[channel_type], fig_path[channel_type] = boxplot_std_hovering_plotly(std_data=rmse[channel_type], tit=channel_names[channel_type], channel_names=channels[channel_type], sid=sid)
        
        df_std[channel_type] = RMSE_meg_epoch(ch_type=channel_type, channels=channels[channel_type], std_lvl=std_lvl, n_events=n_events, df_epochs=df_epochs[channel_type], sid=sid) 

        fig_std_epoch[channel_type], fig_path_std_epoch[channel_type] = boxplot_channel_epoch_hovering_plotly(df_mg=df_std[channel_type], ch_type=channel_names[channel_type], sid=sid, what_data='stds')
        
        list_of_figure_paths.append(fig_path[channel_type])
        list_of_figure_paths_std_epoch.append(fig_path_std_epoch[channel_type])
    
    list_of_figure_paths += list_of_figure_paths_std_epoch

    make_RMSE_html_report(sid=sid, what_data='stds', list_of_figure_paths=list_of_figure_paths)



def MEG_QC_measures(sid):

    """This function will call all the QC functions.
    Here goes several sections which will in the future be called over main, but are not yet, since they are in the notebooks"""

    n_events, df_epochs_mags, df_epochs_grads, epochs_channels_mags, epochs_channels_grads, mags, grads, filtered_d, filtered_d_resamp, raw_cropped, raw = initial_stuff(sid)

    channels = {
        'grads': grads,
        'mags': mags,
    }
    channel_names = {
        'grads': 'Gradiometers',
        'mags': 'Magnetometers'
    }
    df_epochs = {
        'grads': df_epochs_grads,
        'mags': df_epochs_mags
    }
    epochs_channels = {
        'grads': epochs_channels_grads,
        'mags': epochs_channels_mags
    }

    config = configparser.ConfigParser()
    config.read('settings.ini')
    # default_section = config['DEFAULT']
    # sid = default_section['sid']

    # RMSE:

    MEG_QC_rmse(sid, config, channels, df_epochs, channel_names, filtered_d_resamp, n_events)



    # _______________Frequency spectrum
    # import PSD_meg_qc as psd #or smth like this - when it's extracted to .py
    psd_section = config['PSD']
    freq_min = psd_section.getint('freq_min') 
    freq_max = psd_section.getint('freq_max') 
    mean_power_per_band_needed = psd_section['mean_power_per_band_needed']
    n_fft = psd_section.getint('n_fft')
    n_per_seg = psd_section.getint('n_per_seg')

    # !! Rewrite these functions to calc mags or grads only
    freqs_mags, freqs_grads, psds_mags, psds_grads, fig_path_m_psd, fig_path_g_psd = Freq_Spectrum_meg(data=filtered_d_resamp, plotflag=True, sid=sid, freq_min=freq_min, freq_max=freq_max, 
     n_fft=n_fft, n_per_seg=n_per_seg, freq_tmin=None, freq_tmax=None, m_names=mags, g_names=grads)

    _,_, fig_path_m_pie, fig_path_g_pie = Power_of_freq_meg(mags=mags, grads=grads, freqs_mags=freqs_mags, freqs_grads=freqs_grads, psds_mags=psds_mags, psds_grads=psds_grads, mean_power_per_band_needed=mean_power_per_band_needed, plotflag=True, sid=sid)

    from universal_html_report import make_PSD_report
    list_of_figure_paths=[fig_path_m_psd, fig_path_g_psd, fig_path_m_pie, fig_path_g_pie]
    make_PSD_report(sid=sid, list_of_figure_paths=list_of_figure_paths)


    # Peaks manual (mine):
    # from Peaks_meg_qc import peak_amplitude_per_epoch as pp_epoch 
    ptp_manual_section = config['PTP_manual']
    pair_dist_sec = ptp_manual_section.getint('pair_dist_sec') 
    thresh_lvl = ptp_manual_section.getint('thresh_lvl')

    sfreq = filtered_d_resamp.info['sfreq']
    df_pp_ampl_mags=peak_amplitude_per_epoch(mg_names=mags, df_epoch_mg=df_epochs_mags, sfreq=sfreq, n_events=n_events, thresh_lvl=thresh_lvl, pair_dist_sec=pair_dist_sec)
    df_pp_ampl_grads=peak_amplitude_per_epoch(mg_names=grads, df_epoch_mg=df_epochs_grads, sfreq=sfreq, n_events=n_events, thresh_lvl=thresh_lvl, pair_dist_sec=pair_dist_sec)

    from universal_plots import boxplot_channel_epoch_hovering_plotly
    _, fig_path_m_pp_ampl_epoch=boxplot_channel_epoch_hovering_plotly(df_mg=df_pp_ampl_mags, ch_type='Magnetometers', sid='1', what_data='peaks')
    _, fig_path_g_pp_ampl_epoch=boxplot_channel_epoch_hovering_plotly(df_mg=df_pp_ampl_grads, ch_type='Gradiometers', sid='1', what_data='peaks')

    from universal_html_report import make_peak_html_report
    list_of_figure_paths=[fig_path_m_pp_ampl_epoch, fig_path_g_pp_ampl_epoch]
    make_peak_html_report(sid=sid, what_data='peaks', list_of_figure_paths=list_of_figure_paths)



    # Peaks auto (from mne):
    # import peaks_mne #or smth like this - when it's extracted to .py

    ptp_mne_section = config['PTP_mne']

    if default_section['mags_or_grads'] == 'mags':
        peak = ptp_mne_section.getint('peak_m') 
        flat = ptp_mne_section.getint('flat_m') 
        df_ptp_amlitude_annot_mags, bad_channels_mags, amplit_annot_with_ch_names_mags=get_amplitude_annots_per_channel(raw_cropped, peak, flat, ch_type_names=mags)
    elif default_section['mags_or_grads'] == 'grads':
        peak = ptp_mne_section.getint('peak_g') 
        flat = ptp_mne_section.getint('flat_g') 
        df_ptp_amlitude_annot_grads, bad_channels_grads, amplit_annot_with_ch_names_grads=get_amplitude_annots_per_channel(raw_cropped, peak, flat, ch_type_names=grads)
    elif default_section['mags_or_grads'] == 'both':
        peak = ptp_mne_section.getint('peak_m') 
        flat = ptp_mne_section.getint('flat_m') 
        df_ptp_amlitude_annot_mags, bad_channels_mags, amplit_annot_with_ch_names_mags=get_amplitude_annots_per_channel(raw_cropped, peak, flat, ch_type_names=mags)
        peak = ptp_mne_section.getint('peak_g') 
        flat = ptp_mne_section.getint('flat_g') 
        df_ptp_amlitude_annot_grads, bad_channels_grads, amplit_annot_with_ch_names_grads=get_amplitude_annots_per_channel(raw_cropped, peak, flat, ch_type_names=grads)
    # shorten this if thing?


#Run the pipleine over subjects
#  UNCOMMENT THIS PART ONLY WHEN ALL MEASUREMENTS ARE SAVED INTO PY FILES. OTHERWISE IT WILL TRY TO RUN IT AND FAIL EVERY TIME THIS FILE IS CALLED IN ANY WAY
# for sid in sid_list:
#     n_events, df_epochs_mags, df_epochs_grads, epochs_mags, epochs_grads, mags, grads, raw_bandpass, raw_bandpass_resamp, raw_cropped, raw = initial_stuff(sid)
#     MEG_QC_measures(sid)

