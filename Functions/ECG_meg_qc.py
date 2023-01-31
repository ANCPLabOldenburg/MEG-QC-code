import mne
import numpy as np
from universal_plots import QC_derivative, get_tit_and_unit
import plotly.graph_objects as go
from scipy.signal import find_peaks


class Mean_artifact_with_peak:
    """Contains average ecg epoch for a particular channel,
    calculates its main peak (location and magnitude),
    info if this magnitude is concidered as artifact or not."""

    def __init__(self, name: str, mean_artifact_epoch:list, peak_loc=None, peak_magnitude=None, r_wave_shape:bool=None, artif_over_threshold:bool=None):
        self.name =  name
        self.mean_artifact_epoch = mean_artifact_epoch
        self.peak_loc = peak_loc
        self.peak_magnitude = peak_magnitude
        self.r_wave_shape =  r_wave_shape
        self.artif_over_threshold = artif_over_threshold

    def __repr__(self):
        return 'Mean artifact peak on: ' + str(self.name) + '\n - peak location inside artifact epoch: ' + str(self.peak_loc) + '\n - peak magnitude: ' + str(self.peak_magnitude) + '\n r_wave_shape: '+ str(self.r_wave_shape) + '\n - artifact magnitude over threshold: ' + str(self.artif_over_threshold)+ '\n'
    
    def find_peak_and_detect_Rwave(self, max_n_peaks_allowed, thresh_lvl_peakfinder=None):
        
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

        return peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg


    def find_peak_old(self, max_n_peaks_allowed, thresh_lvl_peakfinder=None):

        '''Detects the location and magnitude of the peaks of data, sets them as attributes of the instance.
        Checks if the peak looks like R  wave (ECG) shape or like EOG artifact shape: 
        - either only 1 peak found 
        OR:
        - should have not more  than 5  peaks found - for ECG or not more than 3 - for EOG (otherwise - too noisy) 
        and
        - the highest found peak should be at least a little higher than  average of all found peaks.'''

        #use peak detection: find the locations of prominent peaks (no matter pos or negative), find the amplitude of these peaks.
        #in this case we can set it we find just 1 peak or all the peaks above some peak threshold
        thresh_mean=(max(self.mean_artifact_epoch) - min(self.mean_artifact_epoch)) / thresh_lvl_peakfinder
        
        # peak_locs_pos, peak_magnitudes_pos = mne.preprocessing.peak_finder(self.mean_artifact_epoch, extrema=1, verbose=False, thresh=thresh_mean) 
        # peak_locs_neg, peak_magnitudes_neg = mne.preprocessing.peak_finder(self.mean_artifact_epoch, extrema=-1, verbose=False, thresh=thresh_mean) 

        peak_locs_pos, _ = find_peaks(self.mean_artifact_epoch, prominence=thresh_mean)
        peak_magnitudes_pos=self.mean_artifact_epoch[peak_locs_pos]
        peak_locs_neg, _ = find_peaks(-self.mean_artifact_epoch, prominence=thresh_mean)
        peak_magnitudes_neg=self.mean_artifact_epoch[peak_locs_neg]
        
        peak_locs=np.concatenate((peak_locs_pos, peak_locs_neg), axis=None)
        peak_magnitudes=np.concatenate((peak_magnitudes_pos, peak_magnitudes_neg), axis=None)

        #if there is a peak which is significantly higher than all other peaks - use this one as top of the ECG R wave
        #if not - keep  all peaks. In this case this is not an R wave shape.
        if len(peak_locs)==1:
            self.peak_loc =peak_locs
            self.r_wave_shape=True
            print('___MEG QC___: ', self.name + ': only 1 good peak')
        elif 1<len(peak_locs)<=max_n_peaks_allowed: # and np.max(np.abs(peak_magnitudes))>=peak_magnitudes[np.argmax(np.abs(peak_magnitudes))-1]*1.1:
            #check that max peak is significantly higher than next highest peak
            self.peak_loc =peak_locs
            self.r_wave_shape=True
            print('___MEG QC___: ', self.name + ': found 1 good peak out of several')
        elif len(peak_locs)>=max_n_peaks_allowed:
            self.peak_loc =peak_locs
            self.r_wave_shape=False
            print('___MEG QC___: ', self.name + ': too many peaks, no expected artifact wave shape.')
        elif len(peak_locs)==0: #if no peaks found - simply take the max of the whole epoch
            self.peak_loc=np.array([np.argmax(np.abs(self.mean_artifact_epoch))])
            self.r_wave_shape=False
            print('___MEG QC___: ', self.name + ': no peaks found. Just take largest value as peak.')
        else:
            self.peak_loc =peak_locs
            self.r_wave_shape=False
            print('___MEG QC___: ', self.name + ': no expected artifact wave shape, check the reason!')

        self.peak_magnitude=np.array(self.mean_artifact_epoch[self.peak_loc])

        return

    def plot_epoch_and_peak(self, fig, t, fig_tit, ch_type):

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


def epochs_or_channels_over_limit(norm_lvl, list_mean_ecg_epochs, mean_ecg_magnitude_peak, t, t0_actual):


    timelimit_min=-0.01+t0_actual
    timelimit_max=0.01+t0_actual


    #Find the channels which got peaks over this mean:
    affected_channels=[]
    not_affected_channels=[]
    artifact_lvl=mean_ecg_magnitude_peak/norm_lvl #data over this level will be counted as artifact contaminated
    for potentially_affected_channel in list_mean_ecg_epochs:
        #if np.max(np.abs(potentially_affected_channel.peak_magnitude))>abs(artifact_lvl) and potentially_affected_channel.r_wave_shape is True:
        
        max_peak_magn_ind=np.argmax(potentially_affected_channel.peak_magnitude)

        if potentially_affected_channel.peak_magnitude[max_peak_magn_ind]>abs(artifact_lvl) and timelimit_min<t[potentially_affected_channel.peak_loc[max_peak_magn_ind]]<timelimit_max and potentially_affected_channel.r_wave_shape is True:

            #if peak magnitude (1 peak, not the whole data!) is higher or lower than  the artifact level  AND the peak has r wave shape.
            potentially_affected_channel.artif_over_threshold=True
            affected_channels.append(potentially_affected_channel)
        else:
            not_affected_channels.append(potentially_affected_channel)
            print('___MEG QC___: ', potentially_affected_channel.name, ' Peak magn over th: ', potentially_affected_channel.peak_magnitude[max_peak_magn_ind]>abs(artifact_lvl), ', in the time window: ', timelimit_min<t[potentially_affected_channel.peak_loc[max_peak_magn_ind]]<timelimit_max, ' Rwave: ', potentially_affected_channel.r_wave_shape )

    return affected_channels, not_affected_channels, artifact_lvl


def make_ecg_affected_plots(ecg_affected_channels, artifact_lvl, t, ch_type: str, fig_tit, use_abs_of_all_data):

    fig_ch_tit, unit = get_tit_and_unit(ch_type)

    fig=go.Figure()

    for ch in ecg_affected_channels:
        fig=ch.plot_epoch_and_peak(fig, t, 'Channels affected by ECG artifact: ', ch_type)

    fig.add_trace(go.Scatter(x=t, y=[(artifact_lvl)]*len(t), name='Thres=mean_peak/norm_lvl'))

    if use_abs_of_all_data == 'False':
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


def find_epoch_peaks(ch_data, thresh_lvl_peakfinder):

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


def flip_condition(ecg_or_eog: str, avg_ecg_epoch_data_nonflipped, channels, t, max_n_peaks_allowed, thresh_lvl_peakfinder):
    
    ''' trying another ecg flip approach:

    1. find peaks on all channels it time frame around -0.02<t[peak_loc]<0.012 (here R wave is typica;ly dettected by mne - for ecg, for eog it is -0.1<t[peak_loc]<0.2)
    2. take 5 channels with most prominent peak 
    3. find estimated average t0 for all 5 channels, because t0 of event which mne estimated is often not accurate
    4. flip all channels with negative peak around estimated t0 

    Then (after this function is done):
    5. calculate average of all channels
    6. find peak on average channel and set it as actual t0
    7. affected channels will be the ones which have peak amplitude over average in limits of -0.05:0.05s from actual t0 '''

    if ecg_or_eog=='ECG':
        timelimit_min=-0.02
        timelimit_max=0.012
    elif ecg_or_eog=='EOG':
        timelimit_min=-0.1
        timelimit_max=0.2
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

    # window of 0.01s around t0_estimated where the peak on different channels should be detected:
    t0_estimated_ind_start=np.argwhere(t==round(t0_estimated-0.01, 3))[0][0] 
    t0_estimated_ind_end=np.argwhere(t==round(t0_estimated+0.01, 3))[0][0]
    #yes you have to round it here because the numbers stored in in memery like 0.010000003 even when it looks like 0.01, hence np.where cant find the target float in t vector


    #another way without round would be to find the closest index of t to t0_estimated-0.01:
    #t0_estimated_ind_start=np.argwhere(t==np.min(t[t<t0_estimated-0.01]))[0][0]
    # find the closest index of t to t0_estimated+0.01:
    #t0_estimated_ind_end=np.argwhere(t==np.min(t[t>t0_estimated+0.01]))[0][0]

    print('___MEG QC___: ', t0_estimated_ind, '-t0_estimated_ind, ', t0_estimated, '-t0_estimated,     ', t0_estimated_ind_start, '-t0_estimated_ind_start, ', t0_estimated_ind_end, '-t0_estimated_ind_end')

    
    #find which channels to flip:
    ecg_epoch_per_ch_only_data=np.empty_like(avg_ecg_epoch_data_nonflipped)
    ecg_epoch_per_ch=[]

    for i, ch_data in enumerate(avg_ecg_epoch_data_nonflipped): 
        ecg_epoch_nonflipped = Mean_artifact_with_peak(name=channels[i], mean_artifact_epoch=ch_data)
        peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg = ecg_epoch_nonflipped.find_peak_and_detect_Rwave(max_n_peaks_allowed, thresh_lvl_peakfinder)
        

        #find peak_locs_neg which is located betwenn -0.01<t0_estimated_ind<0.01:
        peak_locs_neg_near_t0=peak_locs_neg[np.argwhere((peak_locs_neg>t0_estimated_ind_start) & (peak_locs_neg<t0_estimated_ind_end))]
        peak_locs_pos_near_t0=peak_locs_pos[np.argwhere((peak_locs_pos>t0_estimated_ind_start) & (peak_locs_pos<t0_estimated_ind_end))]

        print('___MEG QC___: ', peak_locs_neg_near_t0, '-peak_locs_neg_near_t0, ', peak_locs_neg, '-peak_locs_neg')
        print('___MEG QC___: ', peak_locs_pos_near_t0, 'peak_locs_pos_near_t0, ', peak_locs_pos, 'peak_locs_pos')
        
        #keep only negative values in peak_locs_neg_near_t0_ind, because only negative values should be flipped (peak detected could have detected positive but still low values as negative peaks):
        peak_locs_neg_near_t0=np.array([p for p in peak_locs_neg_near_t0 if ch_data[p]<0])

        print('___MEG QC___: ', peak_locs_neg_near_t0, 'peak_locs_neg_near_t0 new')

        #if both neg and pos peaks in the time window were detected, and if the index of negative peak is closer to t0_estimated_ind than index of positive peak - flip the data:
        if (peak_locs_neg_near_t0.size>0) & (peak_locs_pos_near_t0.size>0):

            #find pos and neg peaks which are the closest to t0_estimated_ind:
            peak_locs_neg_near_t0 = peak_locs_neg_near_t0[np.argmin(np.abs(peak_locs_neg_near_t0-t0_estimated_ind))]
            peak_locs_pos_near_t0 = peak_locs_pos_near_t0[np.argmin(np.abs(peak_locs_pos_near_t0-t0_estimated_ind))]

            print('___MEG QC___: ', 'closest:', peak_locs_neg_near_t0, '-peak_locs_neg_near_t0_ind, ', peak_locs_pos_near_t0, '-peak_locs_pos_near_t0_ind')

            if np.abs(peak_locs_neg_near_t0-t0_estimated_ind)<np.abs(peak_locs_pos_near_t0-t0_estimated_ind):
                #flip the data:
                ecg_epoch_per_ch_only_data[i]=-ch_data
                peak_magnitudes_neg=-peak_magnitudes_neg
                peak_magnitudes_pos=-peak_magnitudes_pos
                print('___MEG QC___: ', channels[i]+' was flipped. Negative peak was closer to estomated t0.')
            else:
                ecg_epoch_per_ch_only_data[i]=ch_data
                print('___MEG QC___: ', channels[i]+' was not flipped.')

        #if only negative peak in the time window was detected - flip the data:
        elif (peak_locs_neg_near_t0.size>0) & (peak_locs_pos_near_t0.size==0):
            ecg_epoch_per_ch_only_data[i]=-ch_data
            peak_magnitudes_neg=-peak_magnitudes_neg
            peak_magnitudes_pos=-peak_magnitudes_pos
            print('___MEG QC___: ', channels[i]+' was flipped. Only negative peak was detected.')
        
        # otherwise dont flip:
        else:
            ecg_epoch_per_ch_only_data[i]=ch_data
            print('___MEG QC___: ', channels[i]+' was not flipped.')

        peak_locs=np.concatenate((peak_locs_pos, peak_locs_neg), axis=None)
        peak_magnitudes=np.concatenate((peak_magnitudes_pos, peak_magnitudes_neg), axis=None)

        ecg_epoch_per_ch.append(Mean_artifact_with_peak(name=channels[i], mean_artifact_epoch=ecg_epoch_per_ch_only_data[i], peak_loc=peak_locs, peak_magnitude=peak_magnitudes, r_wave_shape=ecg_epoch_nonflipped.r_wave_shape))

    return ecg_epoch_per_ch, ecg_epoch_per_ch_only_data


def flip_condition_ECG_old(ch_data, ch_name, t, max_n_peaks_allowed, peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg):

    peak_locs=np.concatenate((peak_locs_pos, peak_locs_neg), axis=None)
    peak_magnitudes=np.concatenate((peak_magnitudes_pos, peak_magnitudes_neg), axis=None)

    if np.size(peak_locs_pos)+np.size(peak_locs_neg)>max_n_peaks_allowed: #if too many peaks were detected - do not flip - bad ecg.
        print('___MEG QC___: ', ch_name+' has too many peaks - not R wave shape.')
        return ch_data, peak_magnitudes, peak_locs
    elif np.size(peak_locs_pos)>0 and np.size(peak_locs_neg)==0: #if only positive peaks were detected
        # max_peak_loc_pos=peak_locs_pos[np.argmax(peak_magnitudes_pos)]
        # if -0.02<t[max_peak_loc_pos]<0.012: 
        #     ch_data_new  = ch_data
        #     peak_magnitudes_new = peak_magnitudes
        #     print('___MEG QC___: ', ch_name+' was NOT flipped. -0.02<t[max_peak_loc_pos]<0.012')
        # else: 
        #     ch_data_new  = -ch_data
        #     peak_magnitudes_new=-peak_magnitudes
        #     print('___MEG QC___: ', ch_name+' was flipped. Positive peak is far from time 0 - not the R wave peak - flip')
        ch_data_new  = ch_data
        peak_magnitudes_new = peak_magnitudes
        print('___MEG QC___: ', ch_name+' was NOT flipped. Only positive peaks.')
        
    elif np.size(peak_locs_pos)==0 and np.size(peak_locs_neg)>0: #if only negative peaks were detected
        ch_data_new  = -ch_data
        peak_magnitudes_new=-peak_magnitudes
        print('___MEG QC___: ', ch_name+' was flipped. Only negative peaks were detected.')
    elif np.size(peak_locs_pos)==0 and np.size(peak_locs_neg)==0: #if no peaks were detected
        ch_data_new  = ch_data 
        peak_magnitudes_new = np.array([np.max(ch_data)]) #if no peaks were detected, the max peak magnitude is the max of the whole data. Can be not a peak at all
        peak_locs = np.array([np.argmax(ch_data)])
        print('___MEG QC___: ', ch_name+' was NOT flipped. No peaks were detected.')
    else: #if both positive and negative peaks were detected
        max_peak_magnitude_pos=peak_magnitudes_pos[np.argmax(peak_magnitudes_pos)]
        max_peak_loc_pos=peak_locs_pos[np.argmax(peak_magnitudes_pos)]
        min_peak_magnitude_neg=peak_magnitudes_neg[np.argmin(peak_magnitudes_neg)]
        min_peak_loc_neg=peak_locs_neg[np.argmin(peak_magnitudes_neg)]

        # COMPLEX APPROACH
        # if -0.02<t[max_peak_loc_pos]<0.012: #if the positive peak is close to time 0 - it can be the R wave peak - still need to check if the negative peak is closer to time 0
        #     if min_peak_magnitude_neg<0 and abs(t[min_peak_loc_neg])<=abs(t[max_peak_loc_pos]): # and abs(min_peak_magnitude_neg)>abs(max_peak_magnitude_pos):#min_peak_loc_neg<max_peak_loc_pos: 
        #         ch_data_new  = -ch_data 
        #         peak_magnitudes_new=-peak_magnitudes
        #         print('___MEG QC___: ', ch_name+' was flipped. Both peaks were detected. Upper peak close to time0. Down peak is closer to time0 of the event then the positive peak. And it also is higher than the positive peak.')
        #     else:
        #         ch_data_new  = ch_data 
        #         peak_magnitudes_new = peak_magnitudes
        #         print('___MEG QC___: ', ch_name+' was NOT flipped. Both peaks were detected. Upper peak close to time0. Down peak may be not close enough to time0 or is smaller than positive.')
        # else: #if the positive peak is NOT close to time 0 - check if the negative peak is close to time 0 and is higher than the positive peak
 
        #     if min_peak_magnitude_neg<0 and -0.02<t[min_peak_loc_neg]<0.012: #and abs(min_peak_magnitude_neg)>abs(max_peak_magnitude_pos):
        #         #min_peak_magnitude_neg<0 and -0.02<t[min_peak_loc_neg]<0.012 and abs(min_peak_magnitude_neg)>abs(max_peak_magnitude_pos):
        #         ch_data_new  = -ch_data 
        #         peak_magnitudes_new=-peak_magnitudes
        #         print('___MEG QC___: ', ch_name+' was flipped. Both peaks were detected. Upper peak far from time0 is close enough to time0- flip.')
        #     else:
        #         ch_data_new  = ch_data 
        #         peak_magnitudes_new = peak_magnitudes
        #         print('___MEG QC___: ', ch_name+' was NOT flipped. Both peaks were detected. Upper peak far from time0. But down peak also far.')

        #SIMPLE APPROACH
        # if peak is negative and close to time 0 and is closer than positive - flip:
        if min_peak_magnitude_neg<0 and -0.02<t[min_peak_loc_neg]<0.012 and abs(t[min_peak_loc_neg])<=abs(t[max_peak_loc_pos]): 
            ch_data_new  = -ch_data 
            peak_magnitudes_new=-peak_magnitudes
            print('___MEG QC___: ', ch_name+' was flipped. Both peaks were detected. Peak is negative and close to time 0 and is closer than positive - flip.')
        else:
            ch_data_new  = ch_data 
            peak_magnitudes_new = peak_magnitudes
            print('___MEG QC___: ', ch_name+' was NOT flipped.')

    return ch_data_new, peak_magnitudes_new, peak_locs


def flip_condition_EOG(ch_data, ch_name, t, max_n_peaks_allowed, peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg):

    peak_locs=np.concatenate((peak_locs_pos, peak_locs_neg), axis=None)
    peak_magnitudes=np.concatenate((peak_magnitudes_pos, peak_magnitudes_neg), axis=None)

    if np.size(peak_locs_pos)+np.size(peak_locs_neg)>max_n_peaks_allowed: #if too many peaks were detected - do not flip - bad ecg.
        print('___MEG QC___: ', ch_name+' : EOG epoch is too noisy.')
        return ch_data, peak_magnitudes, peak_locs
    
    if np.size(peak_locs_pos)>0 and np.size(peak_locs_neg)>0: #both positive and negative peaks were detected
        max_peak_magnitude_pos=peak_magnitudes_pos[np.argmax(peak_magnitudes_pos)]
        min_peak_magnitude_neg=peak_magnitudes_neg[np.argmin(peak_magnitudes_neg)]
        if np.min(peak_magnitudes_neg)<0 and abs(min_peak_magnitude_neg)>abs(max_peak_magnitude_pos): 
            ch_data_new  = -ch_data
            peak_magnitudes_new=-peak_magnitudes
            print('___MEG QC___: ', ch_name+' was flipped. Negative peak was larger than positive.')
        else:
            ch_data_new  = ch_data
            peak_magnitudes_new = peak_magnitudes
            print('___MEG QC___: ', ch_name+' was NOT flipped.')
    elif np.size(peak_locs_pos)==0 and np.size(peak_locs_neg)>0: #only negative peaks were detected
        ch_data_new  = -ch_data
        peak_magnitudes_new=-peak_magnitudes
        print('___MEG QC___: ', ch_name+' was flipped. Only negative peaks were detected.')
    else:
        ch_data_new  = ch_data
        peak_magnitudes_new = peak_magnitudes
        print('___MEG QC___: ', ch_name+' was NOT flipped.')

    return ch_data_new, peak_magnitudes_new, peak_locs


def find_affected_channels(ecg_epochs: mne.Epochs, channels: list, m_or_g: str, norm_lvl: float, ecg_or_eog: str, thresh_lvl_peakfinder: float, sfreq:float, tmin: float, tmax: float, plotflag=True, use_abs_of_all_data=False):

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

    3. Compare:
    a) found peaks will be compared across channels to decide which channels are affected the most:
    -Average the peak magnitude over all channels. 
    -Find all channels, where the magnitude is abover average by some level.
    OR
    b) found peaks will be compared across ecg epochs to decide which epochs arestrong.

    Output:
    ecg_affected_channels: list of instances of Mean_artif_peak_on_channel
    2  figures: ecg affected + not affected channels OR epochs.

'''

    if  ecg_or_eog=='ECG':
        max_n_peaks_allowed_per_ms=8 
    elif ecg_or_eog=='EOG':
        max_n_peaks_allowed_per_ms=5
    else:
        print('___MEG QC___: ', '___MEG QC___: ', 'Choose ecg_or_eog input correctly!')

    max_n_peaks_allowed=((abs(tmin)+abs(tmax))/0.1)*max_n_peaks_allowed_per_ms
    print('___MEG QC___: ', 'max_n_peaks_allowed: '+str(max_n_peaks_allowed))

    t = np.round(np.arange(tmin, tmax+1/sfreq, 1/sfreq), 3) #yes, you need to round


    #1.:
    #averaging the ECG epochs together:
    avg_ecg_epochs = ecg_epochs.average(picks=channels)#.apply_baseline((-0.5, -0.2))
    #avg_ecg_epochs is evoked:Evoked objects typically store EEG or MEG signals that have been averaged over multiple epochs.
    #The data in an Evoked object are stored in an array of shape (n_channels, n_times)

    ecg_epoch_per_ch=[]
    if use_abs_of_all_data == 'True':
        ecg_epoch_per_ch_only_data=np.abs(avg_ecg_epochs.data)
        for i, ch_data in enumerate(ecg_epoch_per_ch_only_data):
            ecg_epoch_per_ch.append(Mean_artifact_with_peak(name=channels[i], mean_artifact_epoch=ch_data))
            ecg_epoch_per_ch[i].find_peak_and_detect_Rwave(max_n_peaks_allowed, thresh_lvl_peakfinder)

    elif use_abs_of_all_data == 'False':
        ecg_epoch_per_ch_only_data=avg_ecg_epochs.data
        for i, ch_data in enumerate(ecg_epoch_per_ch_only_data):
            ecg_epoch_per_ch.append(Mean_artifact_with_peak(name=channels[i], mean_artifact_epoch=ch_data))
            ecg_epoch_per_ch[i].find_peak_and_detect_Rwave(max_n_peaks_allowed, thresh_lvl_peakfinder)

    elif use_abs_of_all_data == 'flip':

        avg_ecg_epoch_data_nonflipped=avg_ecg_epochs.data

        ecg_epoch_per_ch, ecg_epoch_per_ch_only_data = flip_condition(ecg_or_eog, avg_ecg_epoch_data_nonflipped, channels, t, max_n_peaks_allowed, thresh_lvl_peakfinder)

        #make_ecg_affected_plots(ecg_epoch_per_ch, 0, t, ch_type=m_or_g, fig_tit=ecg_or_eog+' after flip!: ', use_abs_of_all_data=use_abs_of_all_data)

        # Old version:
        # ecg_epoch_per_ch_only_data=np.empty_like(avg_ecg_epoch_data_nonflipped)

        # for i, ch_data in enumerate(avg_ecg_epoch_data_nonflipped): 
        #     ecg_epoch_nonflipped = Mean_artifact_with_peak(name=channels[i], mean_artifact_epoch=ch_data)
        #     peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg = ecg_epoch_nonflipped.find_peak_and_detect_Rwave(max_n_peaks_allowed, thresh_lvl_peakfinder)
        #     if  ecg_or_eog=='ECG':
        #         ch_data_new, peak_magnitudes_new, peak_locs = flip_condition_ECG_old(ch_data, channels[i], t, max_n_peaks_allowed, peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg)
        #     elif ecg_or_eog=='EOG':
        #         ch_data_new, peak_magnitudes_new, peak_locs = flip_condition_EOG(ch_data, channels[i], t, max_n_peaks_allowed, peak_locs_pos, peak_locs_neg, peak_magnitudes_pos, peak_magnitudes_neg)
        #     ecg_epoch_per_ch_only_data[i]=ch_data_new
        #     ecg_epoch_per_ch.append(Mean_artifact_with_peak(name=channels[i], mean_artifact_epoch=ch_data_new, peak_loc=peak_locs, peak_magnitude=peak_magnitudes_new, r_wave_shape=ecg_epoch_nonflipped.r_wave_shape))
            
    else:
        print('___MEG QC___: ', 'Wrong set variable: use_abs_of_all_data=', use_abs_of_all_data)


    avg_ecg_overall=np.mean(ecg_epoch_per_ch_only_data, axis=0) 
    # will show if there is ecg artifact present  on average. should have ecg shape if yes. 
    # otherwise - it was not picked up/reconstructed correctly

    avg_ecg_overall_obj=Mean_artifact_with_peak(name='Mean_'+ecg_or_eog+'_overall',mean_artifact_epoch=avg_ecg_overall)
    avg_ecg_overall_obj.find_peak_and_detect_Rwave(max_n_peaks_allowed, thresh_lvl_peakfinder)
    mean_ecg_magnitude_peak=np.max(avg_ecg_overall_obj.peak_magnitude)
    mean_ecg_loc_peak = avg_ecg_overall_obj.peak_loc[np.argmax(avg_ecg_overall_obj.peak_magnitude)]
    
    #set t0_actual as the time of the peak of the average ecg artifact:
    t0_actual=t[mean_ecg_loc_peak]

    if avg_ecg_overall_obj.r_wave_shape is True:
        print('___MEG QC___: ', "GOOD " +ecg_or_eog+ " average.")
    else:
        print('___MEG QC___: ', "BAD " +ecg_or_eog+ " average - no typical ECG peak.")


    if plotflag is True:
        fig_avg = go.Figure()
        avg_ecg_overall_obj.plot_epoch_and_peak(fig_avg, t, 'Mean '+ecg_or_eog+' artifact over all data: ', m_or_g)
        fig_avg.show()

    #2. and 3.:
    ecg_affected_channels, ecg_not_affected_channels, artifact_lvl = epochs_or_channels_over_limit(norm_lvl=norm_lvl, list_mean_ecg_epochs=ecg_epoch_per_ch, mean_ecg_magnitude_peak=mean_ecg_magnitude_peak, t=t, t0_actual=t0_actual)

    if plotflag is True:
        fig_affected = make_ecg_affected_plots(ecg_affected_channels, artifact_lvl, t, ch_type=m_or_g, fig_tit=ecg_or_eog+' affected channels: ', use_abs_of_all_data=use_abs_of_all_data)
        fig_not_affected = make_ecg_affected_plots(ecg_not_affected_channels, artifact_lvl, t, ch_type=m_or_g, fig_tit=ecg_or_eog+' not affected channels: ', use_abs_of_all_data=use_abs_of_all_data)

    if avg_ecg_overall_obj.r_wave_shape is False and (not ecg_not_affected_channels or len(ecg_not_affected_channels)/len(channels)<0.2):
        print('___MEG QC___: ', 'Something went wrong! The overall average ' +ecg_or_eog+ ' is  bad, but all  channels are affected by ' +ecg_or_eog+ ' artifact.')

    return ecg_affected_channels, fig_affected, fig_not_affected, fig_avg



#%%
def make_simple_metric_ECG_EOG(all_affected_channels, m_or_g, ecg_or_eog, channels):
    """
    Make simple metric for ECG/EOG artifacts.
    """

    title, unit = get_tit_and_unit(m_or_g)

    affected_chs={}
    for ch in all_affected_channels:
        affected_chs[ch.name]=max(ch.peak_magnitude)

    simple_metric={}

    if not all_affected_channels:
        simple_metric[title+'. Number of '+ecg_or_eog+' affected channels'] = 0
        simple_metric[title+'. Percentage of '+ecg_or_eog+' affected channels'] = 0
        return simple_metric

    simple_metric[title+'. Number of '+ecg_or_eog+' affected channels'] = len(all_affected_channels)
    simple_metric[title+'. Percentage of '+ecg_or_eog+' affected channels'] = round(len(all_affected_channels)/len(channels)*100, 1)
    simple_metric['Details: affected channels'] = [{'Average ' +ecg_or_eog+' peak magnitude in '+unit:  affected_chs}]

    #sort list of channels with peaks  based on the hight of the main peak,  then output the highest 10:
    top_magnitudes = sorted(all_affected_channels, key=lambda x: max(x.peak_magnitude), reverse=True)
    top_10_magnitudes = [[ch_peak.name, max(ch_peak.peak_magnitude)] for ch_peak in top_magnitudes[0:10]]
    simple_metric['Details: affected channels'].append({title+'. Top 10 '+ecg_or_eog+' channels with highest peak magnitude in '+unit: top_10_magnitudes})

    return simple_metric

#%%
def ECG_meg_qc(ecg_params: dict, raw: mne.io.Raw, channels, m_or_g_chosen: list):
    """Main ECG function"""

    ecg_events, ch_ecg, average_pulse, ecg_data=mne.preprocessing.find_ecg_events(raw, return_ecg=True, verbose=False)

    if ch_ecg:
        print('___MEG QC___: ', 'ECG channel used to identify hearbeats: ', raw.info['chs'][ch_ecg]['ch_name'])
    else:
        print('___MEG QC___: ', 'No ECG channel found. The signal is reconstructed based  of magnetometers data.')
    print('___MEG QC___: ', 'Average pulse: ', round(average_pulse), ' per minute') 

    ecg_events_times  = (ecg_events[:, 0] - raw.first_samp) / raw.info['sfreq']
    
    sfreq=raw.info['sfreq']
    tmin=ecg_params['ecg_epoch_tmin']
    tmax=ecg_params['ecg_epoch_tmax']
    norm_lvl=ecg_params['norm_lvl']
    use_abs_of_all_data=ecg_params['use_abs_of_all_data']
    
    ecg_derivs = []
    all_ecg_affected_channels={}
    simple_metric_ECG={}

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

        ecg_affected_channels, fig_affected, fig_not_affected, fig_avg=find_affected_channels(ecg_epochs, channels[m_or_g], m_or_g, norm_lvl, ecg_or_eog='ECG', thresh_lvl_peakfinder=6, tmin=tmin, tmax=tmax, plotflag=True, sfreq=sfreq, use_abs_of_all_data=use_abs_of_all_data)
        ecg_derivs += [QC_derivative(fig_affected, 'ECG_affected_channels_'+m_or_g, 'plotly')]
        ecg_derivs += [QC_derivative(fig_not_affected, 'ECG_not_affected_channels_'+m_or_g, 'plotly')]
        ecg_derivs += [QC_derivative(fig_avg, 'overall_average_ECG_epoch_'+m_or_g, 'plotly')]
        all_ecg_affected_channels[m_or_g]=ecg_affected_channels

        simple_metric_ECG[m_or_g]=make_simple_metric_ECG_EOG(all_ecg_affected_channels[m_or_g], m_or_g, 'ECG', channels[m_or_g])

    return ecg_derivs, simple_metric_ECG, ecg_events_times, all_ecg_affected_channels