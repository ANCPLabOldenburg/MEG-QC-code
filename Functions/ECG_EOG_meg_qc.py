import mne
import numpy as np
from universal_plots import QC_derivative, get_tit_and_unit
from universal_html_report import simple_metric_basic
import plotly.graph_objects as go
from scipy.signal import find_peaks

def detect_noisy_ecg_eog(raw: mne.io.Raw, picked_channels_ecg_or_eog: list[str],  thresh_lvl: float, ecg_or_eog: str, plotflag: bool):
    """Detects noisy ecg or eog channels.

    The channel is noisy when:
    1. There are too many peaks in the data (more frequent than possible heartbets or blinks of a healthy human).
    2. There are too many breaks in the data (indicating lack of heartbeats or blinks for a too long period).

    Parameters
    ----------
    raw : mne.io.Raw
        Raw data.
    picked_channels_ecg_or_eog : list[str]
        List of ECH or EOG channel names to be checked.
    thresh_lvl : float
        Threshold level for peak detection.
    ecg_or_eog : str
        'ECG' or 'EOG'.
    plotflag : bool
        If True, plots the data and detected peaks.

    Returns
    -------
    noisy_ch_derivs : list[QC_derivative]
        List of figures (requested channels plots)  as QC_derivative instances.
    bad_ecg_eog : dict
        Dictionary with channel names as keys and 'good' or 'bad' as values.


    """

    sfreq=raw.info['sfreq']
    #threshold for peak detection. to what level allowed the noisy peaks to be in comparison with most of other peaks
    duration_crop = len(raw)/raw.info['sfreq']/60  #duration in minutes


    if ecg_or_eog == 'ECG' or ecg_or_eog == 'ecg':
            max_peak_dist=35 #allow the lowest pulse to be 35/min. this is the maximal possible distance between 2 pulses.

    elif ecg_or_eog == 'EOG' or ecg_or_eog == 'eog':
            max_peak_dist=5 #normal spontaneous blink rate is between 12 and 15/min, allow 5 blinks a min minimum. However do we really need to limit here?

    bad_ecg_eog = {}
    for picked in picked_channels_ecg_or_eog:
        bad_ecg_eog[picked] = 'good'

        ch_data=raw.get_data(picks=picked)[0] 
        # get_data creates list inside of a list becausee expects to create a list for each channel. 
        # but interation takes 1 ch at a time anyways. this is why [0]
        thresh=(max(ch_data) - min(ch_data)) / thresh_lvl 

        pos_peak_locs, pos_peak_magnitudes = mne.preprocessing.peak_finder(ch_data, extrema=1, thresh=thresh, verbose=False) #positive peaks
        neg_peak_locs, neg_peak_magnitudes = mne.preprocessing.peak_finder(ch_data, extrema=-1, thresh=thresh, verbose=False) #negative peaks

        #find where places of recording without peaks at all:
        normal_pos_peak_locs, _ = mne.preprocessing.peak_finder(ch_data, extrema=1, verbose=False) #all positive peaks of the data
        ind_break_start = np.where(np.diff(normal_pos_peak_locs)/sfreq/60>max_peak_dist)#find where the distance between positive peaks is too long

        #_, amplitudes=neighbour_peak_amplitude(max_pair_dist_sec,sfreq, pos_peak_locs, neg_peak_locs, pos_peak_magnitudes, neg_peak_magnitudes)
        # if amplitudes is not None and len(amplitudes)>3*duration_crop/60: #allow 3 non-standard peaks per minute. Or 0? DISCUSS
        #     bad_ecg_eog=True
        #     print('___MEG QC___: ', picked, ' channel is too noisy. Number of unusual amplitudes detected over the set limit: '+str(len (amplitudes)))

        all_peaks=np.concatenate((pos_peak_locs,neg_peak_locs),axis=None)
        if len(all_peaks)/duration_crop>3:
        # allow 3 non-standard peaks per minute. Or 0? DISCUSS. implies that noiseness has to be repeated regularly.  
        # if there is only 1 little piece of time with noise and the rest is good, will not show that one. 
        # include some time limitation of noisy times?
            bad_ecg_eog[picked] = 'bad'
            print('___MEG QC___: ', 'ECG channel might be corrupted. Atypical peaks in ECG amplitudes detected: '+str(len (all_peaks))+'. Peaks per minute: '+str(round(len(all_peaks)/duration_crop)))

        if len(ind_break_start[0])/duration_crop>3: #allow 3 breaks per minute. Or 0? DISCUSS
            #ind_break_start[0] - here[0] because np.where created array of arrays above
            bad_ecg_eog[picked] = 'bad'
            print('___MEG QC___: ', picked, ' channel has breaks in recording. Number of breaks detected: '+str(len(ind_break_start[0]))+'. Breaks per minute: '+str(round(len(ind_break_start[0])/duration_crop)))

        noisy_ch_derivs=[]
        if plotflag:
            t=np.arange(0, duration_crop, 1/60/sfreq) 
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=t, y=ch_data, name=picked+' data'));
            fig.add_trace(go.Scatter(x=t[pos_peak_locs], y=pos_peak_magnitudes, mode='markers', name='+peak'));
            fig.add_trace(go.Scatter(x=t[neg_peak_locs], y=neg_peak_magnitudes, mode='markers', name='-peak'));

            for n in ind_break_start[0]:
                fig.add_vline(x=t[normal_pos_peak_locs][n],
                annotation_text='break', annotation_position="bottom right",line_width=0.6,annotation=dict(font_size=8))

            fig.update_layout(
                title={
                'text': picked+": peaks and breaks. Channel is "+bad_ecg_eog[picked],
                'y':0.85,
                'x':0.5,
                'xanchor': 'center',
                'yanchor': 'top'},
                xaxis_title="Time in minutes",
                yaxis = dict(
                    showexponent = 'all',
                    exponentformat = 'e'))
                
            fig.show()
            noisy_ch_derivs += [QC_derivative(fig, 'Noisy_ECG_channel', 'plotly')]

    return noisy_ch_derivs, bad_ecg_eog


class Mean_artifact_with_peak:
    """ 
    
    Contains average ecg epoch for a particular channel,
    calculates its main peak (location and magnitude),
    info if this magnitude is concidered as artifact or not.
    
    Attributes
    ----------
    name : str
        name of the channel
    mean_artifact_epoch : list
        list of floats, average ecg epoch for a particular channel
    peak_loc : int
        locations of peaks inside the artifact epoch
    peak_magnitude : float
        magnitudes of peaks inside the artifact epoch
    r_wave_shape : bool
        True if the average epoch has typical wave shape, False otherwise. R wave shape  - for ECG or just a wave shape for EOG.
    artif_over_threshold : bool
        True if the main peak is concidered as artifact, False otherwise. True if artifact sas magnitude over the threshold
    main_peak_loc : int
        location of the main peak inside the artifact epoch
    main_peak_magnitude : float
        magnitude of the main peak inside the artifact epoch

    Methods
    -------
    __init__(self, name: str, mean_artifact_epoch:list, peak_loc=None, peak_magnitude=None, r_wave_shape:bool=None, artif_over_threshold:bool=None, main_peak_loc: int=None, main_peak_magnitude: float=None)
        Constructor
    __repr__(self)
        Returns a string representation of the object



    """

    def __init__(self, name: str, mean_artifact_epoch:list, peak_loc=None, peak_magnitude=None, r_wave_shape:bool=None, artif_over_threshold:bool=None, main_peak_loc: int=None, main_peak_magnitude: float=None):
        '''Constructor'''
        
        self.name =  name
        self.mean_artifact_epoch = mean_artifact_epoch
        self.peak_loc = peak_loc
        self.peak_magnitude = peak_magnitude
        self.r_wave_shape =  r_wave_shape
        self.artif_over_threshold = artif_over_threshold
        self.main_peak_loc = main_peak_loc
        self.main_peak_magnitude = main_peak_magnitude

    def __repr__(self):
        '''Returns a string representation of the object'''
        return 'Mean artifact peak on: ' + str(self.name) + '\n - peak location inside artifact epoch: ' + str(self.peak_loc) + '\n - peak magnitude: ' + str(self.peak_magnitude) +'\n - main_peak_loc: '+ str(self.main_peak_loc) +'\n - main_peak_magnitude: '+str(self.main_peak_magnitude)+'\n r_wave_shape: '+ str(self.r_wave_shape) + '\n - artifact magnitude over threshold: ' + str(self.artif_over_threshold)+ '\n'
    
    def find_peaks_and_detect_Rwave(self, max_n_peaks_allowed, thresh_lvl_peakfinder=None):

        '''Finds peaks in the average artifact epoch and detects if the main peak is R wave shape or not.
        
        Parameters
        ----------
        max_n_peaks_allowed : int
            maximum number of peaks allowed in the average artifact epoch
        thresh_lvl_peakfinder : float
            threshold for peakfinder function
            
        Returns
        -------
        peak_loc : list
            locations of peaks inside the artifact epoch
        peak_magnitudes : list
            magnitudes of peaks inside the artifact epoch
        peak_locs_pos : list
            locations of positive peaks inside the artifact epoch
        peak_locs_neg : list
            locations of negative peaks inside the artifact epoch
        peak_magnitudes_pos : list
            magnitudes of positive peaks inside the artifact epoch
        peak_magnitudes_neg : list
            magnitudes of negative peaks inside the artifact epoch'''
        
        peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg = find_epoch_peaks(ch_data=self.mean_artifact_epoch, thresh_lvl_peakfinder=thresh_lvl_peakfinder)
        
        self.peak_loc=np.concatenate((peak_locs_pos, peak_locs_neg), axis=None)

        if np.size(self.peak_loc)==0: #no peaks found - set peaks as just max of the whole epoch
            self.peak_loc=np.array([np.argmax(np.abs(self.mean_artifact_epoch))])
            self.r_wave_shape=False
        elif 1<=len(self.peak_loc)<=max_n_peaks_allowed:
            self.r_wave_shape=True
        elif len(self.peak_loc)>max_n_peaks_allowed:
            self.r_wave_shape=False
        else:
            self.r_wave_shape=False
            print('___MEG QC___: ', self.name + ': no expected artifact wave shape, check the reason!')

        self.peak_magnitude=np.array(self.mean_artifact_epoch[self.peak_loc])

        peak_locs=np.concatenate((peak_locs_pos, peak_locs_neg), axis=None)
        peak_magnitudes=np.concatenate((peak_magnitudes_pos, peak_magnitudes_neg), axis=None)

        return peak_locs, peak_magnitudes, peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg


    def plot_epoch_and_peak(self, fig, t, fig_tit, ch_type):

        '''Plots the average artifact epoch and the peak inside it.

        Parameters
        ----------
        fig : plotly.graph_objects.Figure
            figure to plot the epoch and the peak
        t : list
            time vector
        fig_tit: str
            title of the figure
        ch_type: str
            type of the channel ('mag, 'grad')

        Returns
        -------
        fig : plotly.graph_objects.Figure
            figure with the epoch and the peak'''

        fig_ch_tit, unit = get_tit_and_unit(ch_type)

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

    def find_largest_peak_in_timewindow(self, t: np.ndarray, timelimit_min: float, timelimit_max: float):

        '''Find the highest peak of the artifact epoch inside the give time wndow. 
        Time window is centered around the t0 of the ecg/eog event and limited by timelimit_min and timelimit_max.
        
        Parameters
        ----------
        t : list
            time vector
        timelimit_min : float
            minimum time limit for the peak
        timelimit_max : float
            maximum time limit for the peak
            
        Returns
        -------
        main_peak_magnitude : float
            magnitude of the main peak
        main_peak_loc : int
            location of the main peak'''

        if self.peak_loc is None:
            self.main_peak_magnitude=None
            self.main_peak_loc=None
            return None, None

        self.main_peak_magnitude = -1000
        for peak_loc in self.peak_loc:
            if timelimit_min<t[peak_loc]<timelimit_max: #if peak is inside the timelimit_min and timelimit_max was found:
                if self.mean_artifact_epoch[peak_loc] > self.main_peak_magnitude: #if this peak is higher than the previous one:
                    self.main_peak_magnitude=self.mean_artifact_epoch[peak_loc]
                    self.main_peak_loc=peak_loc 
  
        if self.main_peak_magnitude == -1000: #if no peak was found inside the timelimit_min and timelimit_max:
            self.main_peak_magnitude=None
            self.main_peak_loc=None

        return self.main_peak_loc, self.main_peak_magnitude


def detect_channels_above_norm(norm_lvl: float, list_mean_ecg_epochs: list, mean_ecg_magnitude_peak: float, t: np.ndarray, t0_actual: float, ecg_or_eog: str):

    '''Find the channels which got average artifact amplitude higher than the average over all channels*norm_lvl.
    
    Parameters
    ----------
    norm_lvl : float
        The norm level is the scaling factor for the threshold. The mean artifact amplitude over all channels is multiplied by the norm_lvl to get the threshold.
    list_mean_ecg_epochs : list
        List of MeanArtifactEpoch objects, each hold the information about mean artifact for one channel.
    mean_ecg_magnitude_peak : float
        The magnitude the mean artifact amplitude over all channels.
    t : np.ndarray
        Time vector.
    t0_actual : float
        The time of the ecg/eog event.
    ecg_or_eog : str
        Either 'ECG' or 'EOG'.

    Returns
    -------
    affected_channels : list
        List of channels which got average artifact amplitude higher than the average over all channels*norm_lvl. -> affected by ECG/EOG artifact
    not_affected_channels : list
        List of channels which got average artifact amplitude lower than the average over all channels*norm_lvl. -> not affected by ECG/EOG artifact
    artifact_lvl : float
        The threshold for the artifact amplitude: average over all channels*norm_lvl.
        '''


    if ecg_or_eog=='ECG':
        window_size=0.02
    elif ecg_or_eog=='EOG':
        window_size=0.1
    else:
        print('___MEG QC___: ', 'ecg_or_eog should be either ECG or EOG')

    timelimit_min=-window_size+t0_actual
    timelimit_max=window_size+t0_actual


    #Find the channels which got peaks over this mean:
    affected_channels=[]
    not_affected_channels=[]
    artifact_lvl=mean_ecg_magnitude_peak/norm_lvl #data over this level will be counted as artifact contaminated
    for potentially_affected_channel in list_mean_ecg_epochs:
        #if np.max(np.abs(potentially_affected_channel.peak_magnitude))>abs(artifact_lvl) and potentially_affected_channel.r_wave_shape is True:


        #find the highest peak inside the timelimit_min and timelimit_max:
        main_peak_loc, main_peak_magnitude = potentially_affected_channel.find_largest_peak_in_timewindow(t, timelimit_min, timelimit_max)

        print('___MEG QC___: ', potentially_affected_channel.name, ' Main Peak magn: ', potentially_affected_channel.main_peak_magnitude, ', Main peak loc ', potentially_affected_channel.main_peak_loc, ' Rwave: ', potentially_affected_channel.r_wave_shape)
        
        if main_peak_magnitude is not None: #if there is a peak in time window of artifact - check if it s high enough and has right shape
            if main_peak_magnitude>abs(artifact_lvl) and potentially_affected_channel.r_wave_shape is True:
                potentially_affected_channel.artif_over_threshold=True
                affected_channels.append(potentially_affected_channel)
            else:
                not_affected_channels.append(potentially_affected_channel)
                print('___MEG QC___: ', potentially_affected_channel.name, ' Peak magn over th: ', potentially_affected_channel.main_peak_magnitude>abs(artifact_lvl), ', in the time window: ', potentially_affected_channel.main_peak_loc, ' Rwave: ', potentially_affected_channel.r_wave_shape)
        else:
            not_affected_channels.append(potentially_affected_channel)
            print('___MEG QC___: ', potentially_affected_channel.name, ' Peak magn over th: NO PEAK in time window')

    return affected_channels, not_affected_channels, artifact_lvl


def plot_affected_channels(ecg_affected_channels: list, artifact_lvl: float, t: np.ndarray, ch_type: str, fig_tit: str, flip_data: bool or str = 'flip'):

    '''Plot the mean artifact amplitude for all affected (not affected) channels in 1 plot together with the artifact_lvl.
    
    Parameters
    ----------
    ecg_affected_channels : list
        List of ECG/EOG artifact affected channels.
    artifact_lvl : float
        The threshold for the artifact amplitude: average over all channels*norm_lvl.
    t : np.ndarray
        Time vector.
    ch_type : str
        Either 'mag' or 'grad'.
    fig_tit: str
        The title of the figure.
    flip_data : bool
        If True, the absolute value of the data will be used for the calculation of the mean artifact amplitude. Default to 'flip'. 
        'flip' means that the data will be flipped if the peak of the artifact is negative. 
        This is donr to get the same sign of the artifact for all channels, then to get the mean artifact amplitude over all channels and the threshold for the artifact amplitude onbase of this mean
        And also for the reasons of visualization: the artifact amplitude is always positive.

    Returns
    -------
    fig : plotly.graph_objects.Figure
        The plotly figure with the mean artifact amplitude for all affected (not affected) channels in 1 plot together with the artifact_lvl.

'''

    fig_ch_tit, unit = get_tit_and_unit(ch_type)

    fig=go.Figure()

    for ch in ecg_affected_channels:
        fig=ch.plot_epoch_and_peak(fig, t, 'Channels affected by ECG artifact: ', ch_type)

    fig.add_trace(go.Scatter(x=t, y=[(artifact_lvl)]*len(t), name='Thres=mean_peak/norm_lvl'))

    if flip_data == 'False':
        fig.add_trace(go.Scatter(x=t, y=[(-artifact_lvl)]*len(t), name='-Thres=mean_peak/norm_lvl'))

    fig.update_layout(
        xaxis_title='Time in seconds',
        yaxis = dict(
            showexponent = 'all',
            exponentformat = 'e'),
        yaxis_title='Mean artifact magnitude in '+unit,
        title={
            'text': fig_tit+str(len(ecg_affected_channels))+' '+fig_ch_tit,
            'y':0.85,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'})


    fig.show()

    return fig


def find_epoch_peaks(ch_data: np.ndarray, thresh_lvl_peakfinder: float):
    '''Find the peaks in the epoch data using the peakfinder algorithm.

    Parameters
    ----------
    ch_data : np.ndarray
        The data of the channel.
    thresh_lvl_peakfinder : float
        The threshold for the peakfinder algorithm.

    Returns
    -------
    peak_locs_pos : np.ndarray
        The locations of the positive peaks.
    peak_locs_neg : np.ndarray
        The locations of the negative peaks.
    peak_magnitudes_pos : np.ndarray
        The magnitudes of the positive peaks.
    peak_magnitudes_neg : np.ndarray
        The magnitudes of the negative peaks.

    '''

    thresh_mean=(max(ch_data) - min(ch_data)) / thresh_lvl_peakfinder
    peak_locs_pos, _ = find_peaks(ch_data, prominence=thresh_mean)
    peak_locs_neg, _ = find_peaks(-ch_data, prominence=thresh_mean)

    try:
        peak_magnitudes_pos=ch_data[peak_locs_pos]
    except:
        peak_magnitudes_pos=np.empty(0)

    try:
        peak_magnitudes_neg=ch_data[peak_locs_neg]
    except:
        peak_magnitudes_neg=np.empty(0)

    return peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg



def flip_channels(avg_ecg_epoch_data_nonflipped: np.ndarray, channels: list, max_n_peaks_allowed: int, thresh_lvl_peakfinder: float, t0_estimated_ind_start: int, t0_estimated_ind_end: int, t0_estimated_ind: int):

    '''Flip the channels if the peak of the artifact is negative and located close to the estimated t0.

    Parameters
    ----------
    avg_ecg_epoch_data_nonflipped : np.ndarray
        The data of the channels.
    channels : list
        The list of the channels.
    max_n_peaks_allowed : int
        The maximum number of peaks allowed in the epoch.
    thresh_lvl_peakfinder : float
        The threshold for the peakfinder algorithm.
    t0_estimated_ind_start : int
        The start index of the time window for the estimated t0.
    t0_estimated_ind_end : int
        The end index of the time window for the estimated t0.
    t0_estimated_ind : int
        The index of the estimated t0.


    Returns
    -------
    ecg_epoch_per_ch : list
        The list of the ecg epochs.
    avg_ecg_epoch_per_ch_only_data : np.ndarray
        The data of the channels after flipping.


    '''

    ecg_epoch_per_ch_only_data=np.empty_like(avg_ecg_epoch_data_nonflipped)
    ecg_epoch_per_ch=[]

    for i, ch_data in enumerate(avg_ecg_epoch_data_nonflipped): 
        ecg_epoch_nonflipped = Mean_artifact_with_peak(name=channels[i], mean_artifact_epoch=ch_data)
        peak_locs, peak_magnitudes, _, _, _, _ = ecg_epoch_nonflipped.find_peaks_and_detect_Rwave(max_n_peaks_allowed, thresh_lvl_peakfinder)
        #print('___MEG QC___: ', channels[i], ' peak_locs:', peak_locs)

        #find peak_locs which is located the closest to t0_estimated_ind:
        if peak_locs.size>0:
            peak_loc_closest_to_t0=peak_locs[np.argmin(np.abs(peak_locs-t0_estimated_ind))]

        #if peak_loc_closest_t0 is negative and is located in the estimated time window of the wave - flip the data:
        if (ch_data[peak_loc_closest_to_t0]<0) & (peak_loc_closest_to_t0>t0_estimated_ind_start) & (peak_loc_closest_to_t0<t0_estimated_ind_end):
            ecg_epoch_per_ch_only_data[i]=-ch_data
            peak_magnitudes=-peak_magnitudes
            #print('___MEG QC___: ', channels[i]+' was flipped: peak_loc_near_t0: ', peak_loc_closest_to_t0, t[peak_loc_closest_to_t0], ', peak_magn:', ch_data[peak_loc_closest_to_t0], ', t0_estimated_ind_start: ', t0_estimated_ind_start, t[t0_estimated_ind_start], 't0_estimated_ind_end: ', t0_estimated_ind_end, t[t0_estimated_ind_end])
        else:
            ecg_epoch_per_ch_only_data[i]=ch_data
            #print('___MEG QC___: ', channels[i]+' was NOT flipped: peak_loc_near_t0: ', peak_loc_closest_to_t0, t[peak_loc_closest_to_t0], ', peak_magn:', ch_data[peak_loc_closest_to_t0], ', t0_estimated_ind_start: ', t0_estimated_ind_start, t[t0_estimated_ind_start], 't0_estimated_ind_end: ', t0_estimated_ind_end, t[t0_estimated_ind_end])

        ecg_epoch_per_ch.append(Mean_artifact_with_peak(name=channels[i], mean_artifact_epoch=ecg_epoch_per_ch_only_data[i], peak_loc=peak_locs, peak_magnitude=peak_magnitudes, r_wave_shape=ecg_epoch_nonflipped.r_wave_shape))

    return ecg_epoch_per_ch, ecg_epoch_per_ch_only_data


def estimate_t0(ecg_or_eog: str, avg_ecg_epoch_data_nonflipped: list, t: np.ndarray):
    
    ''' 
    Estimate t0 for the artifact. MNE has it s own estomation of t0, but it is often not accurate.
    1. find peaks on all channels in time frame around -0.02<t[peak_loc]<0.012 (here R wave is typically dettected by mne - for ecg, for eog it is -0.1<t[peak_loc]<0.2)
    2. take 5 channels with most prominent peak 
    3. find estimated average t0 for all 5 channels, because t0 of event which mne estimated is often not accurate.
    
    Parameters
    ----------
    ecg_or_eog : str
        The type of the artifact: 'ECG' or 'EOG'.
    avg_ecg_epoch_data_nonflipped : np.ndarray
        The data of the channels.
    t : np.ndarray
        The time vector.
        
    Returns
    -------
    t0_estimated_ind : int
        The index of the estimated t0.
    t0_estimated : float
        The estimated t0.
    t0_estimated_ind_start : int
        The start index of the time window for the estimated t0.
    t0_estimated_ind_end : int
        The end index of the time window for the estimated t0.
    
    '''
    

    if ecg_or_eog=='ECG':
        timelimit_min=-0.02
        timelimit_max=0.012
        window_size=0.02
    elif ecg_or_eog=='EOG':
        timelimit_min=-0.1
        timelimit_max=0.2
        window_size=0.1

        #these define different windows: 
        # - timelimit is where the peak of the wave is normally located counted from event time defined by mne. 
        #       It is a larger window, it is used to estimate t0, more accurately than mne does (based on 5 most promiment channels).
        # - window_size - where the peak of the wave must be located, counted from already estimated t0. It is a smaller window.
    else:
        print('___MEG QC___: ', 'Choose ecg_or_eog input correctly!')


    #find indexes of t where t is between timelimit_min and timelimit_max (limits where R wave typically is detected by mne):
    t_event_ind=np.argwhere((t>timelimit_min) & (t<timelimit_max))

    # cut the data of each channel to the time interval where R wave is expected to be:
    avg_ecg_epoch_data_nonflipped_limited_to_event=avg_ecg_epoch_data_nonflipped[:,t_event_ind[0][0]:t_event_ind[-1][0]]

    #find 5 channels with max values in the time interval where R wave is expected to be:
    max_values=np.max(np.abs(avg_ecg_epoch_data_nonflipped_limited_to_event), axis=1)
    max_values_ind=np.argsort(max_values)[::-1]
    max_values_ind=max_values_ind[:5]

    # find the index of max value for each of these 5 channels:
    max_values_ind_in_avg_ecg_epoch_data_nonflipped=np.argmax(np.abs(avg_ecg_epoch_data_nonflipped_limited_to_event[max_values_ind]), axis=1)
    
    #find average index of max value for these 5 channels th then derive t0_estimated:
    t0_estimated_average=int(np.round(np.mean(max_values_ind_in_avg_ecg_epoch_data_nonflipped)))
    #limited to event means that the index is limited to the time interval where R wave is expected to be.
    #Now need to get back to actual time interval of the whole epoch:

    #find t0_estimated to use as the point where peak of each ch data should be:
    t0_estimated_ind=t_event_ind[0][0]+t0_estimated_average #sum because time window was cut from the beginning of the epoch previously
    t0_estimated=t[t0_estimated_ind]

    # window of 0.015 or 0.05s around t0_estimated where the peak on different channels should be detected:
    t0_estimated_ind_start=np.argwhere(t==round(t0_estimated-window_size, 3))[0][0] 
    t0_estimated_ind_end=np.argwhere(t==round(t0_estimated+window_size, 3))[0][0]
    #yes you have to round it here because the numbers stored in in memery like 0.010000003 even when it looks like 0.01, hence np.where cant find the target float in t vector


    #another way without round would be to find the closest index of t to t0_estimated-0.015:
    #t0_estimated_ind_start=np.argwhere(t==np.min(t[t<t0_estimated-window_size]))[0][0]
    # find the closest index of t to t0_estimated+0.015:
    #t0_estimated_ind_end=np.argwhere(t==np.min(t[t>t0_estimated+window_size]))[0][0]

    print('___MEG QC___: ', t0_estimated_ind, '-t0_estimated_ind, ', t0_estimated, '-t0_estimated,     ', t0_estimated_ind_start, '-t0_estimated_ind_start, ', t0_estimated_ind_end, '-t0_estimated_ind_end')

    
    return t0_estimated, t0_estimated_ind, t0_estimated_ind_start, t0_estimated_ind_end




def find_affected_channels(ecg_epochs: mne.Epochs, channels: list, m_or_g: str, norm_lvl: float, ecg_or_eog: str, thresh_lvl_peakfinder: float, sfreq:float, tmin: float, tmax: float, plotflag=True, flip_data='flip'):

    '''
    Find channels that are affected by ECG or EOG events.
    The function calculates average ECG epoch for each channel and then finds the peak of the wave on each channel.
    Then it compares the peak amplitudes across channels to decide which channels are affected the most.
    The function returns a list of channels that are affected by ECG or EOG events.

    0. For each separate channel get the average ECG epoch. If needed, flip this average epoch to make it's main peak positive.
        Flip approach: 
        - define  a window around the ecg/eog event deteceted by mne. This is not the real t0, but  an approximation. 
            The size of the window defines by how large on average the error of mne is when mne algorythm estimates even time. 
            So for example if mne is off by 0.05s on average, then the window should be -0.05 to 0.05s. 
        - take 5 channels with the largest peak in this window - assume these peaks are the actual artifact.
        - find the average of these 5 peaks - this is the new estimated_t0 (but still not the real t0)
        - create a new window around this new t0 - in this time window all the artifact wave shapes should be located on all channels.
        - flip the channels, if they have a peak inside of this new window, but the peak is negative and it is the closest peak to estimated t0. 
            if the peak is positive - do not flip.
        - collect all final flipped+unflipped eppochs of these channels 
        
    1. Then, for each chennel make a check if the epoch has a typical wave shape. This is the first step to detect affected channels. 
        If no wave shape - it s automatically a not affected channel. If it has - check further.
        It could make sense to do this step after the next one, but actually check for wave shape is done together with peak detection in step 0. Hence this order)

    2. Calculate average ECG epoch on the collected epochs from all channels. Check if average has a wave shape. 
        If no wave shape - no need to check for affected channels further.
        If it has - check further

    3. Set a threshold which defines a high amplitude of ECG event. (All above this threshold counted as potential ECG peak.)
        Threshold is the magnitude of the peak of the average ECG/EOG epoch multiplued by norm_lvl. 
        norl_lvl is chosen by user in config file
    
    4. Find all peaks above this threshold.
        Finding approach:
        - again, set t0 actual as the time point of the peak of an average artifact (over all channels)
        - again, set a window around t0_actual. this new window is defined by how long the wave of the artifact normally is. 
            The window is centered around t0 and for ECG it will be -0.-02 to 0.02s, for EOG it will be -0.1 to 0.1s.
        - find one main peak of the epoch for each channel which would be inside this window and closest to t0.
        - if this peaks magnitude is over the threshold - this channels is considered to be affected by ECG or EOG. Otherwise - not affected.
            (The epoch has to have a wave shape).

    5. Affected and non affected channels will be plotted and added to the dictionary for final report and json file.


    Parameters
    ----------
    ecg_epochs : mne.Epochs
        ECG epochs.
    channels : list
        List of channels to use.
    m_or_g : str
        'mag' or 'grad'.
    norm_lvl : float
        Normalization level.
    ecg_or_eog : str
        'ECG' or 'EOG'.
    thresh_lvl_peakfinder : float
        Threshold level for peakfinder.
    sfreq : float
        Sampling frequency.
    tmin : float
        Start time.
    tmax : float
        End time.
    plotflag : bool, optional
        Plot flag. The default is True.
    flip_data : bool, optional    
        Use absolute value of all data. The default is 'flip'.

    Returns 
    -------
    ecg_affected_channels : list
        List of instances of Mean_artif_peak_on_channel. The list of channels affected by ecg.eog artifact.
        Each instance contains info about the average ecg/eog artifact on this channel and the peak amplitude of the artifact.
    ecg_not_affected_channels : list
        List of instances of Mean_artif_peak_on_channel. The list of channels not affected by ecg.eog artifact.
        Each instance contains info about the average ecg/eog artifact on this channel and the peak amplitude of the artifact.
    fig_affected : plotly.graph_objects.Figure
        Figure with ecg/eog affected channels.
    fig_not_affected : plotly.graph_objects.Figure
        Figure with ecg/eog not affected channels.
    fig_avg : plotly.graph_objects.Figure
        Figure with average ecg/eog artifact over all channels.
    bad_avg: bool
        True if the average ecg/eog artifact is bad: too noisy. In case of a noisy average ecg/eog artifact, no affected channels should be further detected.

'''

    if  ecg_or_eog=='ECG':
        max_n_peaks_allowed_per_ms=8 
    elif ecg_or_eog=='EOG':
        max_n_peaks_allowed_per_ms=5
    else:
        print('___MEG QC___: ', 'Choose ecg_or_eog input correctly!')

    max_n_peaks_allowed=round(((abs(tmin)+abs(tmax))/0.1)*max_n_peaks_allowed_per_ms)
    print('___MEG QC___: ', 'max_n_peaks_allowed: '+str(max_n_peaks_allowed))

    t = np.round(np.arange(tmin, tmax+1/sfreq, 1/sfreq), 3) #yes, you need to round


    #1.:
    #averaging the ECG epochs together:
    avg_ecg_epochs = ecg_epochs.average(picks=channels)#.apply_baseline((-0.5, -0.2))
    #avg_ecg_epochs is evoked:Evoked objects typically store EEG or MEG signals that have been averaged over multiple epochs.
    #The data in an Evoked object are stored in an array of shape (n_channels, n_times)

    ecg_epoch_per_ch=[]

    if flip_data is False:
        ecg_epoch_per_ch_only_data=avg_ecg_epochs.data
        for i, ch_data in enumerate(ecg_epoch_per_ch_only_data):
            ecg_epoch_per_ch.append(Mean_artifact_with_peak(name=channels[i], mean_artifact_epoch=ch_data))
            ecg_epoch_per_ch[i].find_peaks_and_detect_Rwave(max_n_peaks_allowed, thresh_lvl_peakfinder)

    elif flip_data is True:

        # New ecg flip approach:

        # 1. find peaks on all channels it time frame around -0.02<t[peak_loc]<0.012 (here R wave is typica;ly dettected by mne - for ecg, for eog it is -0.1<t[peak_loc]<0.2)
        # 2. take 5 channels with most prominent peak 
        # 3. find estimated average t0 for all 5 channels, because t0 of event which mne estimated is often not accurate
        # 4. flip all channels with negative peak around estimated t0 


        avg_ecg_epoch_data_nonflipped=avg_ecg_epochs.data

        _, t0_estimated_ind, t0_estimated_ind_start, t0_estimated_ind_end = estimate_t0(ecg_or_eog, avg_ecg_epoch_data_nonflipped, t)
        ecg_epoch_per_ch, ecg_epoch_per_ch_only_data = flip_channels(avg_ecg_epoch_data_nonflipped, channels, max_n_peaks_allowed, thresh_lvl_peakfinder, t0_estimated_ind_start, t0_estimated_ind_end, t0_estimated_ind)

      
    else:
        print('___MEG QC___: ', 'Wrong set variable: flip_data=', flip_data)


    # Find affected channels after flipping:
    # 5. calculate average of all channels
    # 6. find peak on average channel and set it as actual t0
    # 7. affected channels will be the ones which have peak amplitude over average in limits of -0.05:0.05s from actual t0 '''


    avg_ecg_overall=np.mean(ecg_epoch_per_ch_only_data, axis=0) 
    # will show if there is ecg artifact present  on average. should have ecg shape if yes. 
    # otherwise - it was not picked up/reconstructed correctly

    avg_ecg_overall_obj=Mean_artifact_with_peak(name='Mean_'+ecg_or_eog+'_overall',mean_artifact_epoch=avg_ecg_overall)
    avg_ecg_overall_obj.find_peaks_and_detect_Rwave(max_n_peaks_allowed, thresh_lvl_peakfinder)
    mean_ecg_magnitude_peak=np.max(avg_ecg_overall_obj.peak_magnitude)
    mean_ecg_loc_peak = avg_ecg_overall_obj.peak_loc[np.argmax(avg_ecg_overall_obj.peak_magnitude)]
    
    #set t0_actual as the time of the peak of the average ecg artifact:
    t0_actual=t[mean_ecg_loc_peak]

    if avg_ecg_overall_obj.r_wave_shape is True:
        print('___MEG QC___: ', "GOOD " +ecg_or_eog+ " average.")
        bad_avg=False
    else:
        print('___MEG QC___: ', "BAD " +ecg_or_eog+ " average - no typical ECG peak.")
        bad_avg=True


    if plotflag is True:
        fig_avg = go.Figure()
        avg_ecg_overall_obj.plot_epoch_and_peak(fig_avg, t, 'Mean '+ecg_or_eog+' artifact over all data: ', m_or_g)
        fig_avg.show()

    #2. and 3.:
    ecg_affected_channels, ecg_not_affected_channels, artifact_lvl = detect_channels_above_norm(norm_lvl=norm_lvl, list_mean_ecg_epochs=ecg_epoch_per_ch, mean_ecg_magnitude_peak=mean_ecg_magnitude_peak, t=t, t0_actual=t0_actual, ecg_or_eog=ecg_or_eog)

    if plotflag is True:
        fig_affected = plot_affected_channels(ecg_affected_channels, artifact_lvl, t, ch_type=m_or_g, fig_tit=ecg_or_eog+' affected channels: ', flip_data=flip_data)
        fig_not_affected = plot_affected_channels(ecg_not_affected_channels, artifact_lvl, t, ch_type=m_or_g, fig_tit=ecg_or_eog+' not affected channels: ', flip_data=flip_data)

    if avg_ecg_overall_obj.r_wave_shape is False and (not ecg_not_affected_channels or len(ecg_not_affected_channels)/len(channels)<0.2):
        print('___MEG QC___: ', 'Something went wrong! The overall average ' +ecg_or_eog+ ' is  bad, but all  channels are affected by ' +ecg_or_eog+ ' artifact.')

    return ecg_affected_channels, fig_affected, fig_not_affected, fig_avg, bad_avg



#%%
def make_dict_global_ECG_EOG(all_affected_channels: list, channels: list):
    ''' Make a dictionary for the global part of simple metrics for ECG/EOG artifacts.
    For ECG.EOG metric no local metrics are calculated, so global is the only one.
    
    Parameters
    ----------
    all_affected_channels : list
        List of all affected channels.
    channels : list
        List of all channels.
        
    Returns
    -------
    dict_global_ECG_EOG : dict
        Dictionary with simple metrics for ECG/EOG artifacts.

        '''

    if not all_affected_channels:
        number_of_affected_ch = 0
        percent_of_affected_ch = 0
        affected_chs = None
        #top_10_magnitudes = None
    else:
        number_of_affected_ch = len(all_affected_channels)
        percent_of_affected_ch = round(len(all_affected_channels)/len(channels)*100, 1)

        # sort all_affected_channels by main_peak_magnitude:
        all_affected_channels_sorted = sorted(all_affected_channels, key=lambda ch: ch.main_peak_magnitude, reverse=True)
        affected_chs = {ch.name: ch.main_peak_magnitude for ch in all_affected_channels_sorted}

    metric_global_content = {
        'number_of_affected_ch': number_of_affected_ch,
        'percent_of_affected_ch': percent_of_affected_ch, 
        'details':  affected_chs}

    return metric_global_content


def make_simple_metric_ECG_EOG(all_affected_channels: dict, m_or_g_chosen: list, ecg_or_eog: str, channels: dict, bad_avg: dict):
    """ Make simple metric for ECG/EOG artifacts as a dictionary, which will further be converted into json file.
    
    Parameters
    ----------
    all_affected_channels : dict
        Dictionary with lists of affected channels for each channel type.
    m_or_g_chosen : list
        List of channel types chosen for the analysis. 
    ecg_or_eog : str
        String 'ecg' or 'eog' depending on the artifact type.
    channels : dict
        Dictionary with lists of channels for each channel type.
    bad_avg : dict
        Dictionary with boolean values for mag and grad, indicating if the average artifact is bad or not. 
        
    Returns
    -------
    simple_metric : dict
        Dictionary with simple metrics for ECG/EOG artifacts.
        
    """

    metric_global_name = 'all_'+ecg_or_eog+'_affected_channels'
    metric_global_content={'mag': None, 'grad': None}
    metric_global_description = 'Affected channels are the channels with average (over '+ecg_or_eog+' epochs of this channel) ' +ecg_or_eog+ ' artifact above the threshold. Channels are listed here in order from the highest to lowest artifact amplitude. Non affected channels are not listed. Threshld is defined as average '+ecg_or_eog+' artifact peak magnitude over al channels * norm_lvl. norm_lvl is defined in the config file. Metrci also provides a list of 10 most strongly affected channels + their artfact peaks magnitdes.'

    for m_or_g in m_or_g_chosen:
        if bad_avg[m_or_g] is False:
            metric_global_content[m_or_g]= make_dict_global_ECG_EOG(all_affected_channels[m_or_g], channels[m_or_g])

    simple_metric = simple_metric_basic(metric_global_name, metric_global_description, metric_global_content['mag'], metric_global_content['grad'], display_only_global=True)

    return simple_metric

#%%
def ECG_meg_qc(ecg_params: dict, raw: mne.io.Raw, channels: list, m_or_g_chosen: list):
    """Main ECG function. Calculates average ECG artifact and finds affected channels.
    
    Parameters
    ----------
    ecg_params : dict
        Dictionary with ECG parameters originating from config file.
    raw : mne.io.Raw
        Raw data.
    channels : dict
        Dictionary with lists of channels for each channel type (typer mag and grad).
    m_or_g_chosen : list
        List of channel types chosen for the analysis.
        
    Returns
    -------
    ecg_derivs : list
        List of all derivatives (plotly figures) as QC_derivative instances
    simple_metric_ECG : dict
        Dictionary with simple metrics for ECG artifacts to be exported into json file.
    no_ecg_str : str
        String with information about ECG channel used in the final report.
        
    """

    picks_ECG = mne.pick_types(raw.info, ecg=True)
    ecg_ch_name = [raw.info['chs'][name]['ch_name'] for name in picks_ECG]

    ecg_derivs = []

    noisy_ch_derivs, bad_ecg_eog = detect_noisy_ecg_eog(raw, ecg_ch_name,  thresh_lvl = 1, ecg_or_eog = 'ECG', plotflag = True)

    ecg_derivs += noisy_ch_derivs
    if ecg_ch_name:
        for ch in ecg_ch_name:
            if bad_ecg_eog[ch] == 'bad': #ecg channel present but noisy - drop it and  try to reconstruct
                no_ecg_str = 'ECG channel data is too noisy, cardio artifacts were reconstructed. \n'
                print('___MEG QC___:  ECG channel data is too noisy, cardio artifacts reconstruction will be attempted but might not be perfect. Cosider checking the quality of ECG channel on your recording device.')
                raw.drop_channels(ch)
            else:
                no_ecg_str = 'ECG channel used to identify hearbeats: ' + ch + '. \n'
                print('___MEG QC___: ', no_ecg_str)
    else:
        no_ecg_str = 'No ECG channel found. Cardio artifacts were reconstructed. \n'
        print('___MEG QC___: ', 'No ECG channel found. The signal is reconstructed based  of magnetometers data.')
    

    #ecg_events_times  = (ecg_events[:, 0] - raw.first_samp) / raw.info['sfreq']
    
    sfreq=raw.info['sfreq']
    tmin=ecg_params['ecg_epoch_tmin']
    tmax=ecg_params['ecg_epoch_tmax']
    norm_lvl=ecg_params['norm_lvl']
    flip_data=ecg_params['flip_data']
    
    all_ecg_affected_channels={}
    bad_avg = {}

    for m_or_g  in m_or_g_chosen:

        ecg_epochs = mne.preprocessing.create_ecg_epochs(raw, picks=channels[m_or_g], tmin=tmin, tmax=tmax)

        fig_ecg = ecg_epochs.plot_image(combine='mean', picks = m_or_g)[0] #plot averageg over ecg epochs artifact
        # [0] is to plot only 1 figure. the function by default is trying to plot both mag and grad, but here we want 
        # to do them saparetely depending on what was chosen for analysis
        ecg_derivs += [QC_derivative(fig_ecg, 'mean_ECG_epoch_'+m_or_g, 'matplotlib')]
        fig_ecg.show()

        #averaging the ECG epochs together:
        avg_ecg_epochs = ecg_epochs.average() #.apply_baseline((-0.5, -0.2))
        # about baseline see here: https://mne.tools/stable/auto_tutorials/preprocessing/10_preprocessing_overview.html#sphx-glr-auto-tutorials-preprocessing-10-preprocessing-overview-py
    
        fig_ecg_sensors = avg_ecg_epochs.plot_joint(times=[tmin-tmin/100, tmin/2, 0, tmax/2, tmax-tmax/100], picks = m_or_g)
        # tmin+tmin/10 and tmax-tmax/10 is done because mne sometimes has a plotting issue, probably connected tosamplig rate: 
        # for example tmin is  set to -0.05 to 0.02, but it  can only plot between -0.0496 and 0.02.

        #plot average artifact with topomap
        ecg_derivs += [QC_derivative(fig_ecg_sensors, 'ECG_field_pattern_sensors_'+m_or_g, 'matplotlib')]
        fig_ecg_sensors.show()

        ecg_affected_channels, fig_affected, fig_not_affected, fig_avg, bad_avg[m_or_g]=find_affected_channels(ecg_epochs, channels[m_or_g], m_or_g, norm_lvl, ecg_or_eog='ECG', thresh_lvl_peakfinder=6, tmin=tmin, tmax=tmax, plotflag=True, sfreq=sfreq, flip_data=flip_data)
        ecg_derivs += [QC_derivative(fig_affected, 'ECG_affected_channels_'+m_or_g, 'plotly')]
        ecg_derivs += [QC_derivative(fig_not_affected, 'ECG_not_affected_channels_'+m_or_g, 'plotly')]
        ecg_derivs += [QC_derivative(fig_avg, 'overall_average_ECG_epoch_'+m_or_g, 'plotly')]
        all_ecg_affected_channels[m_or_g]=ecg_affected_channels

        if bad_avg[m_or_g] is True:
            tit, _ = get_tit_and_unit(m_or_g)
            no_ecg_str += tit+': ECG signal detection/reconstruction did not produce reliable results. Hearbeat artifacts and affected channels can not be estimated. \n'
        else:
            no_ecg_str += ''

    simple_metric_ECG = make_simple_metric_ECG_EOG(all_ecg_affected_channels, m_or_g_chosen, 'ECG', channels, bad_avg)

    return ecg_derivs, simple_metric_ECG, no_ecg_str


#%%
def EOG_meg_qc(eog_params: dict, raw: mne.io.Raw, channels: dict, m_or_g_chosen: list):
    """Main EOG function. Calculates average EOG artifact and finds affected channels.
    
    Parameters
    ----------
    eog_params : dict
        Dictionary with EOG parameters originating from the config file.
    raw : mne.io.Raw
        Raw MEG data.
    channels : dict
        Dictionary with lists of channels for each channel type (typer mag and grad).
    m_or_g_chosen : list
        List of channel types chosen for the analysis.
        
    Returns
    -------
    eog_derivs : list
        List of all derivatives (plotly figures) as QC_derivative instances
    simple_metric_EOG : dict
        Dictionary with simple metrics for ECG artifacts to be exported into json file.
    no_eog_str : str
        String with information about EOG channel used in the final report."""

    picks_EOG = mne.pick_types(raw.info, eog=True)
    eog_ch_name = [raw.info['chs'][name]['ch_name'] for name in picks_EOG]
    if picks_EOG.size == 0:
        no_eog_str = 'No EOG channels found is this data set - EOG artifacts can not be detected.'
        print('___MEG QC___: ', no_eog_str)
        return None, None, no_eog_str
    else:
        no_eog_str = 'Only blinks can be calculated using MNE, not saccades.'
        print('___MEG QC___: ', 'EOG channels found: ', eog_ch_name)


    eog_derivs = []

    noisy_ch_derivs, bad_ecg_eog = detect_noisy_ecg_eog(raw, eog_ch_name,  thresh_lvl = 1, ecg_or_eog = 'EOG', plotflag = True)
    eog_derivs += noisy_ch_derivs

    for ch_eog in eog_ch_name:
        if bad_ecg_eog[ch_eog] == 'bad': #ecg channel present but noisy give waring, otherwise just contine. 
            #BTW we dont relly care if the bad escg channel is the one for saccades, becase we only use blinks. Identify this in the warning?
            #IDK how because I dont know which channel is the one for saccades
            print('___MEG QC___:  '+ch_eog+' channel data is noisy. EOG data will be estimated, but might not be accurate. Cosider checking the quality of ECG channel on your recording device.')


    #eog_events=mne.preprocessing.find_eog_events(raw, thresh=None, ch_name=None)
    # ch_name: This doesn’t have to be a channel of eog type; it could, for example, also be an ordinary 
    # EEG channel that was placed close to the eyes, like Fp1 or Fp2.
    # or just use none as channel, so the eog will be found automatically

    #eog_events_times  = (eog_events[:, 0] - raw.first_samp) / raw.info['sfreq']

    sfreq=raw.info['sfreq']
    tmin=eog_params['eog_epoch_tmin']
    tmax=eog_params['eog_epoch_tmax']
    norm_lvl=eog_params['norm_lvl']
    flip_data=eog_params['flip_data']

    all_eog_affected_channels={}
    bad_avg = {}
    no_eog_str = ''
    for m_or_g  in m_or_g_chosen:

        eog_epochs = mne.preprocessing.create_eog_epochs(raw, picks=channels[m_or_g], tmin=tmin, tmax=tmax)

        fig_eog = eog_epochs.plot_image(combine='mean', picks = m_or_g)[0]
        eog_derivs += [QC_derivative(fig_eog, 'mean_EOG_epoch_'+m_or_g, 'matplotlib')]

        #averaging the ECG epochs together:
        fig_eog_sensors = eog_epochs.average().plot_joint(picks = m_or_g)
        eog_derivs += [QC_derivative(fig_eog_sensors, 'EOG_field_pattern_sensors_'+m_or_g, 'matplotlib')]

        eog_affected_channels, fig_affected, fig_not_affected, fig_avg, bad_avg[m_or_g] = find_affected_channels(eog_epochs, channels[m_or_g], m_or_g, norm_lvl, ecg_or_eog='EOG', thresh_lvl_peakfinder=2, tmin=tmin, tmax=tmax, plotflag=True, sfreq=sfreq, flip_data=flip_data)
        eog_derivs += [QC_derivative(fig_affected, 'EOG_affected_channels_'+m_or_g, 'plotly')]
        eog_derivs += [QC_derivative(fig_not_affected, 'EOG_not_affected_channels_'+m_or_g, 'plotly')]
        eog_derivs += [QC_derivative(fig_avg, 'overall_average_EOG_epoch_'+m_or_g, 'plotly')]
        all_eog_affected_channels[m_or_g]=eog_affected_channels

        if bad_avg[m_or_g] is True:
            tit, _ = get_tit_and_unit(m_or_g)
            no_eog_str += tit+': EOG signal detection did not produce reliable results. Eyeblink artifacts and affected channels can not be estimated. \n'
        else:
            no_eog_str += ''

    simple_metric_EOG=make_simple_metric_ECG_EOG(all_eog_affected_channels, m_or_g_chosen, 'EOG', channels, bad_avg)

    return eog_derivs, simple_metric_EOG, no_eog_str
