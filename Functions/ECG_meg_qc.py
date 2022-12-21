import mne
import numpy as np
from universal_plots import QC_derivative
import plotly.graph_objects as go

def ECG_meg_qc(ecg_params: dict, raw: mne.io.Raw, m_or_g_chosen: list):
    """Main ECG function"""


    # picks_ECG = mne.pick_types(raw.info, ecg=True)
    # if picks_ECG.size == 0:
    #     print('No ECG channels found is this data set, cardio artifacts can not be detected. ECG data can be reconstructed on base of magnetometers, but this will not be accurate and is not recommended.')
    #     return None, None
    # else:
    #     ECG_channel_name=[]
    #     for i in range(0,len(picks_ECG)):
    #         ECG_channel_name.append(raw.info['chs'][picks_ECG[i]]['ch_name'])

    ecg_events, ch_ecg, average_pulse, ecg_data=mne.preprocessing.find_ecg_events(raw, return_ecg=True, verbose=False)

    if ch_ecg:
        print('ECG channel used to identify hearbeats: ', raw.info['chs'][ch_ecg]['ch_name'])
    else:
        print('No ECG channel found. The signal is reconstructed based  of magnetometers data.')
    print('Average pulse: ', round(average_pulse), ' per minute') 

    ecg_events_times  = (ecg_events[:, 0] - raw.first_samp) / raw.info['sfreq']

    #WHAT SHOULD WE SHOW? CAN PLOT THE ECG CHANNEL. OR ECG EVENTS ON TOP OF 1 OF THE CHANNELS DATA. OR ON EVERY CHANNELS DATA?

    ecg_epochs = mne.preprocessing.create_ecg_epochs(raw)
    avg_ecg_epochs = ecg_epochs.average().apply_baseline((-0.5, -0.2))
    # about baseline see here: https://mne.tools/stable/auto_tutorials/preprocessing/10_preprocessing_overview.html#sphx-glr-auto-tutorials-preprocessing-10-preprocessing-overview-py
    
    ecg_deriv = []

    for m_or_g  in m_or_g_chosen:

        fig_ecg = ecg_epochs.plot_image(combine='mean', picks = m_or_g)[0] #plot averageg over ecg epochs artifact
        # [0] is to plot only 1 figure. the function by default is trying to plot both mag and grad, but here we want 
        # to do them saparetely depending on what was chosen for analysis
        ecg_deriv += [QC_derivative(fig_ecg, 'mean_ECG_epoch_'+m_or_g, None, 'matplotlib')]
        fig_ecg.show()

        #averaging the ECG epochs together:
        avg_ecg_epochs = ecg_epochs.average().apply_baseline((-0.5, -0.2))
        fig_ecg_sensors = avg_ecg_epochs.plot_joint(times=[-0.25, -0.025, 0, 0.025, 0.25], picks = m_or_g)
        #plot average artifact with topomap
        ecg_deriv += [QC_derivative(fig_ecg_sensors, 'ECG_field_pattern_sensors_'+m_or_g, None, 'matplotlib')]
        fig_ecg_sensors.show()

    # Need to output: channels contamminated with ecg artifacts. 

    return ecg_deriv, ecg_events_times

class Mean_artifact_with_peak:
    """Contains average ecg epoch for a particular channel,
    calculates its main peak (location and magnitude),
    info if this magnitude is concidered as artifact or not."""

    def __init__(self, channel_or_epoch:str, mean_artifact_epoch:list, peak_loc=None, peak_magnitude=None, r_wave_shape:bool=None, artif_over_threshold:bool=None):
        self.name =  channel_or_epoch
        self.mean_artifact_epoch = mean_artifact_epoch
        self.peak_loc = peak_loc
        self.peak_magnitude = peak_magnitude
        self.r_wave_shape =  r_wave_shape
        self.artif_over_threshold = artif_over_threshold

    def __repr__(self):
        return 'Mean artifact peak on: ' + str(self.channel_or_epoch) + '\n - peak location inside artifact epoch: ' + str(self.peak_loc) + '\n - peak magnitude: ' + str(self.peak_magnitude) + '\n r_wave_shape: '+ str(self.r_wave_shape) + '\n - artifact magnitude over threshold: ' + str(self.artif_over_threshold)+ '\n'
    
    def find_peak(self, thresh_lvl_peakfinder=None):

        '''Detects the location and magnitude of the peaks of data, sets them as attributes of the instance.
        Checks if the peak looks like R  wave (ECG) shape: 
        - either only 1 peak found 
        OR:
        - should have not more  than 4  peaks found (otherwise - too noisy) 
        and
        - the highest found peak should be at least a little higher than  average of all found peaks.'''

        #use peak detection: find the locations of prominent peaks (no matter pos or negative), find the amplitude of these peaks.
        #in this case we can set it we find just 1 peak or all the peaks above some peak threshold
        thresh_mean=(max(self.mean_artifact_epoch) - min(self.mean_artifact_epoch)) / thresh_lvl_peakfinder
        peak_locs, peak_magnitudes = mne.preprocessing.peak_finder(abs(self.mean_artifact_epoch), extrema=1, verbose=False, thresh=thresh_mean) 
        
        #if there is a peak which is significantly higher than all other peaks - use this one as top of the ECG R wave
        #if not - keep  all peaks. In this case this is not an R wave shape.
        if len(peak_magnitudes)==1:
            self.peak_loc =peak_locs
            self.r_wave_shape=True
            print(self.name + ': only 1 good peak')
        elif 1<len(peak_magnitudes)<5 and np.max(peak_magnitudes)>np.mean(peak_magnitudes)*1.1:
            #self.peak_loc =np.array([peak_locs[np.argmax(peak_magnitudes)]])
            self.peak_loc =peak_locs
            self.r_wave_shape=True
            print(self.name + ': found good peak out of several')
        elif len(peak_magnitudes)>=5:
            self.peak_loc =peak_locs
            self.r_wave_shape=False
            print(self.name + ': too many peaks, no R wave shape.')
        elif len(peak_magnitudes)==0: #if no peaks found - simply take the max of the whole epoch
            self.peak_loc=np.array([np.argmax(np.abs(self.mean_artifact_epoch))])
            self.r_wave_shape=False
            print(self.name + ': no peaks found. Just take largest value as peak.')
        else:
            self.peak_loc =peak_locs
            self.r_wave_shape=False
            print(self.name + ': not R wave shape, check the reason!.')

        self.peak_magnitude=np.array(self.mean_artifact_epoch[self.peak_loc])

        return

    def plot_epoch_and_peak(self, fig, sfreq, tmin, tmax, fig_tit, ch_type):
        if ch_type=='mag':
            fig_ch_tit='Magnetometers'
            unit='Tesla'
        elif ch_type=='grad':
            fig_ch_tit='Gradiometers'
            unit='Tesla/meter'
        else:
            fig_ch_tit='?'
            unit='?unknown unit?'
            print('Please check ch_type input. Has to be "mag" or "grad"')

        t = np.arange(tmin, tmax+1/sfreq, 1/sfreq)

        fig.add_trace(go.Scatter(x=np.array(t), y=np.array(self.mean_artifact_epoch), name=self.name))
        fig.add_trace(go.Scatter(x=np.array(t[self.peak_loc]), y=self.peak_magnitude, mode='markers', name='peak: '+self.name));

        fig.update_layout(
            xaxis_title='Time in seconds',
            yaxis = dict(
                showexponent = 'all',
                exponentformat = 'e'),
            yaxis_title='Mean artifact magnitude in '+unit,
            title={
                'text': fig_tit+fig_ch_tit,
                'y':0.85,
                'x':0.5,
                'xanchor': 'center',
                'yanchor': 'top'})

        return fig


def epochs_or_channels_over_limit(loop_over, thresh_lvl_peakfinder, norm_lvl, list_mean_ecg_epochs):

    #calculate peaks of each mean ecg epoch ():
    ecg_peaks_all_channels=[]
    for ch_ind, ch in enumerate(loop_over):
        ecg_peaks_1ch=Mean_artifact_with_peak(channel_or_epoch=ch, mean_artifact_epoch=list_mean_ecg_epochs[ch_ind])
        
        ecg_peaks_1ch.find_peak(thresh_lvl_peakfinder)
        ecg_peaks_all_channels.append(ecg_peaks_1ch)


    #find mean ECG magnitude over all channels:
    mean_ecg_magnitude = np.mean([np.max(potentially_affected_channel.peak_magnitude) for potentially_affected_channel in ecg_peaks_all_channels])
    #max: of the  all peaks if several we re found inside 1 channel. mean: of the peaks in between diff channels.

    #Find the channels which got peaks over this mean:
    affected_channels=[]
    not_affected_channels=[]
    artifact_lvl=mean_ecg_magnitude/norm_lvl #data over this level will be counted as artifact contamiunated
    for ch_ind, potentially_affected_channel in enumerate(ecg_peaks_all_channels):
        if np.max(np.abs(potentially_affected_channel.peak_magnitude))>abs(artifact_lvl) and potentially_affected_channel.r_wave_shape is True:
            #if peak magnitude (1 peak, not the whole data!) is higher or lower than  the artifact level  AND the peak has r wave shape.
            potentially_affected_channel.artif_over_threshold=True
            affected_channels.append(potentially_affected_channel)
        else:
            not_affected_channels.append(potentially_affected_channel)

    return affected_channels, not_affected_channels, artifact_lvl


def find_ecg_affected_channels(raw: mne.io.Raw, channels:dict, m_or_g_chosen:list, norm_lvl: float, thresh_lvl_peakfinder, tmin=-0.1, tmax=0.1, plotflag=True, use_abs_of_all_data=False):

    '''
    1. Calculate average ECG epoch: 
    a) over all ecg epochs for each channel - to find contamminated channels (this func)
    OR
    b) over all channels for each ecg epoch - to find strongest ecg epochs (next func)

    2.Set some threshold which defines a high amplitude of ECG event. All above this - counted as potential ECG peak.
    (Instead of comparing peak amplitudes could also calculate area under the curve. 
    But peak can be better because data can be so noisy for some channels, that area will be pretty large 
    even when the peak is not present.)
    If there are several peaks above the threshold found - find the biggest one and detect as ecg peak.

    (Peak is detected in a very short area of the ecg epoch: tmin=-0.1, tmax=0.1, instead of tmin=-0.5, tmax=0.5  
    which is default for ecg epoch detectin by mne.
    This is done to detect the central peak more precisely and skip all the non-ecg related fluctuations).

    3. Compare:
    a) found peaks will be compared across channels to decide which channels are affected the most:
    -Average the peak magnitude over all channels. 
    -Find all channels, where the magnitude is abover average by some (SET IT!) level.
    OR
    b) found peaks will be compared across ecg epochs to decide which epochs arestrong.

    Output:
    ecg_affected_channels: list of instances of Mean_artif_peak_on_channel
    2  figures: ecg affected + not affected channels OR epochs.

'''
    
    ecg_affected_channels={}
    ecg_not_affected_channels={}
    all_figs=[]
    for m_or_g in m_or_g_chosen:

        #1.:
        ecg_epochs = mne.preprocessing.create_ecg_epochs(raw, picks=channels[m_or_g], tmin=tmin, tmax=tmax)
        #HERE THINK IF THIS USE OF 'PICKS' IS OK and doesnt prevent ecg reconstruction from mag.
        #according to function description, it should not. parameter ch_name is in charge of what will be used for reconstruction. 
        # but still need to make sure! run some checks.

        #averaging the ECG epochs together:
        avg_ecg_epochs = ecg_epochs.average(picks=channels[m_or_g])#.apply_baseline((-0.5, -0.2))
        #avg_ecg_epochs is evoked:Evoked objects typically store EEG or MEG signals that have been averaged over multiple epochs.
        #The data in an Evoked object are stored in an array of shape (n_channels, n_times)

        if use_abs_of_all_data is True:
            avg_ecg_epoch_data_all=np.abs(avg_ecg_epochs.data)
        else:
            avg_ecg_epoch_data_all=avg_ecg_epochs.data
        
        #2* Check if the detected ECG artifact makes sense: does the average have a prominent peak?
        #avg_ecg_overall=np.mean(np.abs(avg_ecg_epoch_data_all), axis=0) 

        avg_ecg_overall=np.mean(avg_ecg_epoch_data_all, axis=0) 
        # will show if there is ecg artifact present  on average. should hav ecg shape if yes. 
        # otherwise - it was not picked up/resonctructed correctly

        avg_ecg_overall_obj=Mean_artifact_with_peak(channel_or_epoch='Mean_ECG_overall',mean_artifact_epoch=avg_ecg_overall)
        avg_ecg_overall_obj.find_peak(thresh_lvl_peakfinder)
        # thresh_avg=(max(abs(avg_ecg_overall)) - min(abs(avg_ecg_overall)))/2
        # mean_peak_locs, mean_peak_magnitudes = mne.preprocessing.peak_finder(abs(avg_ecg_overall), extrema=1, verbose=False, thresh=thresh_avg) 
    

        if len(avg_ecg_overall_obj.peak_loc)==1 and avg_ecg_overall_obj.r_wave_shape is True:
            print("GOOD ECG average")
        elif len(avg_ecg_overall_obj.peak_loc)>1 and avg_ecg_overall_obj.r_wave_shape is True:
            print("BAD ECG average: too many peaks. Peaks found: " + str(len(avg_ecg_overall_obj.peak_loc)))
            print('Can not identify ECG affected channels, because the average ECG artifact doesnt have a typical ECG peak. \n  See if the recorded or reconstructed ECG signal has issues.')
        elif len(avg_ecg_overall_obj.peak_loc)==1 and avg_ecg_overall_obj.r_wave_shape is False:
            print("BAD ECG average: the found highest peak is too low compared to surrounding data")
            print('Can not identify ECG affected channels, because the average ECG artifact doesnt have a typical ECG peak. \n  See if the recorded or reconstructed ECG signal has issues.')
        elif len(avg_ecg_overall_obj.peak_loc)>1 and avg_ecg_overall_obj.r_wave_shape is False:
            print("BAD ECG average: the found highest peak is too low compared to surrounding data. Too many peaks. Peaks found: " + str(len(avg_ecg_overall_obj.peak_loc)))
            print('Can not identify ECG affected channels, because the average ECG artifact doesnt have a typical ECG peak. \n  See if the recorded or reconstructed ECG signal has issues.')
        else:
            print('Bad ECG average. Unknown reason.')
            #return None, None
  
        if plotflag is True:
            fig_avg = go.Figure()
            avg_ecg_overall_obj.plot_epoch_and_peak(fig_avg, sfreq=raw.info['sfreq'], tmin=tmin, tmax=tmax, fig_tit='Mean ECG artifact over all data: ', ch_type=m_or_g)
            fig_avg.show()


        #2. and 3.:
        affected_channels, not_affected_channels, artifact_lvl = epochs_or_channels_over_limit(loop_over=channels[m_or_g], thresh_lvl_peakfinder=thresh_lvl_peakfinder, norm_lvl=norm_lvl, list_mean_ecg_epochs=avg_ecg_epoch_data_all)

        ecg_affected_channels[m_or_g]=affected_channels
        ecg_not_affected_channels[m_or_g]=not_affected_channels

        if plotflag is True:

            fig_affected=go.Figure()
            sfreq=raw.info['sfreq']
            # fig_affected=plot_affected_channels(raw.info['sfreq'], tmin, tmax, affected_channels, artifact_lvl, 'Channels affected by ECG artifact: ', m_or_g)
            # fig_not_affected=plot_affected_channels(raw.info['sfreq'], tmin, tmax,not_affected_channels, artifact_lvl, 'Channels not affected by ECG artifact: ', m_or_g)
            
            for ch in affected_channels:
                fig_affected=ch.plot_epoch_and_peak(fig_affected, sfreq, tmin=tmin, tmax=tmax, fig_tit='Channels affected by ECG artifact: ', ch_type=m_or_g)
            t = np.arange(tmin, tmax+1/sfreq, 1/sfreq)
            fig_affected.add_trace(go.Scatter(x=t, y=[(artifact_lvl)]*len(t), name='Thres=mean_peak/norm_lvl'))
            fig_affected.add_trace(go.Scatter(x=t, y=[(-artifact_lvl)]*len(t), name='-Thres=mean_peak/norm_lvl'))


            fig_not_affected=go.Figure()
            for ch in not_affected_channels:
                fig_not_affected=ch.plot_epoch_and_peak(fig_not_affected, sfreq, tmin=tmin, tmax=tmax, fig_tit='Channels not affected by ECG artifact: ', ch_type=m_or_g)
            fig_not_affected.add_trace(go.Scatter(x=t, y=[(artifact_lvl)]*len(t), name='Thres=mean_peak/norm_lvl'))
            fig_not_affected.add_trace(go.Scatter(x=t, y=[(-artifact_lvl)]*len(t), name='-Thres=mean_peak/norm_lvl'))

            fig_affected.show()
            fig_not_affected.show()

            all_figs += [fig_affected, fig_not_affected, fig_avg]

        if len(avg_ecg_overall_obj.peak_loc)!=1 and (not ecg_not_affected_channels[m_or_g] or len(ecg_not_affected_channels[m_or_g])/len(channels[m_or_g])<0.2):
            print('Something went wrong! The overall average ECG is  bad, but all  channels are affected by ECG artifact.')

    return ecg_affected_channels, all_figs


def find_ecg_affected_epochs(raw: mne.io.Raw, channels:dict, m_or_g_chosen:list, norm_lvl: float, thresh_lvl_peakfinder, tmin=-0.1, tmax=0.1,plotflag=True):

    ecg_affected_epochs={}
    ecg_not_affected_epochs={}
    all_figs=[]

    for m_or_g in m_or_g_chosen:

        #1.:
        ecg_epochs = mne.preprocessing.create_ecg_epochs(raw, picks=channels[m_or_g], tmin=tmin, tmax=tmax)
        df_ecg_epochs = ecg_epochs.to_data_frame()

        #calculate mean of each time point over all channels. abs value of magnitude is taken.
        df_ecg_epochs['mean'] = df_ecg_epochs.iloc[:, 3:-1].abs().mean(axis=1)

        # Plot to check:
        # fig = go.Figure()
        # sfreq=raw.info['sfreq']
        # t = np.arange(tmin, tmax+1/sfreq, 1/sfreq)

        #collect the mean values of each echepoch into a list
        all_means_of_epochs = [None] * len(ecg_epochs) #preassign
        for ep in range(0,len(ecg_epochs)):
            df_one_ep=df_ecg_epochs.loc[df_ecg_epochs['epoch'] == ep]
            all_means_of_epochs[ep]=np.array(df_one_ep.loc[:,"mean"])

        #     if ep ==0:
        #         fig.add_trace(go.Scatter(x=t, y=all_means_of_epochs[ep], name='epoch '+str(ep)))
        # fig.show()

        epoch_numbers_list=list(range(0, len(ecg_epochs)))
        #2. and 3.:
        strong_ecg_epochs, weak_ecg_epochs, artifact_lvl = epochs_or_channels_over_limit(loop_over=epoch_numbers_list, thresh_lvl_peakfinder=thresh_lvl_peakfinder, norm_lvl=norm_lvl, list_mean_ecg_epochs=all_means_of_epochs)
        ecg_affected_epochs[m_or_g]=strong_ecg_epochs
        ecg_not_affected_epochs[m_or_g]=weak_ecg_epochs

        if plotflag:

            fig_affected=plot_affected_channels(raw.info['sfreq'], tmin, tmax, strong_ecg_epochs, artifact_lvl, 'Strong ECG epochs: ', m_or_g)
            fig_not_affected=plot_affected_channels(raw.info['sfreq'], tmin, tmax, weak_ecg_epochs, artifact_lvl, 'Weak ECG epochs: ', m_or_g)

            all_figs += [fig_affected, fig_not_affected]
    
    return ecg_affected_epochs, all_figs