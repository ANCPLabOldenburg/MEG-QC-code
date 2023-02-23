
# # Annotate muscle artifacts
# 
# Explanation from MNE:
# Muscle contractions produce high frequency activity that can mask brain signal
# of interest. Muscle artifacts can be produced when clenching the jaw,
# swallowing, or twitching a cranial muscle. Muscle artifacts are most
# noticeable in the range of 110-140 Hz.
# 
# This code uses :func:`~mne.preprocessing.annotate_muscle_zscore` to annotate
# segments where muscle activity is likely present. This is done by band-pass
# filtering the data in the 110-140 Hz range. Then, the envelope is taken using
# the hilbert analytical signal to only consider the absolute amplitude and not
# the phase of the high frequency signal. The envelope is z-scored and summed
# across channels and divided by the square root of the number of channels.
# Because muscle artifacts last several hundred milliseconds, a low-pass filter
# is applied on the averaged z-scores at 4 Hz, to remove transient peaks.
# Segments above a set threshold are annotated as ``BAD_muscle``. In addition,
# the ``min_length_good`` parameter determines the cutoff for whether short
# spans of "good data" in between muscle artifacts are included in the
# surrounding "BAD" annotation.
# 


import mne
mne.viz.set_browser_backend('matplotlib')
import plotly.graph_objects as go
from scipy.signal import find_peaks
import numpy as np
from mne.preprocessing import annotate_muscle_zscore
from universal_plots import QC_derivative, get_tit_and_unit

def make_simple_metric_muscle(m_or_g_decided: str, z_scores_dict: dict):

    '''Make a simple metric dict for muscle events.
    
    Parameters
    ----------
    m_or_g_decided : str
        The channel type used for muscle detection: 'mag' or 'grad'.
    z_scores_dict : dict
        The z-score thresholds used for muscle detection.
        
    Returns
    -------
    simple_metric : dict
        A simple metric dict for muscle events.
        
    '''

    simple_metric = {
    'description': 'Muscle artifact events at different z score thresholds.',
    'muscle_calculated_using': m_or_g_decided,
    'unit_muscle_evet_times': 'seconds',
    'unit_muscle_event_zscore': 'z-score',
    'zscore_thresholds': z_scores_dict}

    return simple_metric


def MUSCLE_meg_qc(muscle_params: dict, raw: mne.io.Raw, powerline_freqs: list, m_or_g_chosen:list, interactive_matplot:bool = False):

    '''
    Detect muscle artifacts in MEG data. 
    Gives the number of muscle artifacts based on the set z score threshold: artifact time + artifact z score.
    Threshold  is set by the user in the config file. Several thresholds can be used on the loop.

    Notes
    -----
    The data has to first be notch filtered at powerline frequencies as suggested by mne.


    Parameters
    ----------

    muscle_params : dict
        The parameters for muscle artifact detection originally defined in the config file.
    raw : mne.io.Raw
        The raw data.
    powerline_freqs : list
        The powerline frequencies found in the data by previously running PSD_meg_qc.
    m_or_g_chosen : list
        The channel types chosen for the analysis: 'mag' or 'grad'.
    interactive_matplot : bool
        Whether to use interactive matplotlib plots or not. Default is False because it cant be extracted into the report. 
        But might just be useful for beter undertanding while maintaining this function.

    Returns
    -------
    muscle_derivs : list
        A list of QC_derivative objects for muscle events containing figures.
    simple_metric : dict
        A simple metric dict for muscle events.

    '''


    if 'mag' in m_or_g_chosen:
        m_or_g_decided=['mag']
        print('___MEG QC___: ', 'Muscle artifact detection performed on magnetometers, they are more sensitive to muscle activity than gradiometers.')
    elif 'grad' in m_or_g_chosen and 'mag' not in m_or_g_chosen:
        m_or_g_decided=['grad']
        print('___MEG QC___: ', 'Muscle artifact detection performed on gradiometers. Magnetometers are more sensitive to muscle artifacts then gradiometers and are recommended for artifact detection. If you only use gradiometers, some muscle events might not show. This will not be a problem if the data set only contains gradiometers. But if it contains both gradiometers and magnetometers, but only gradiometers were chosen for this analysis - the results will not include an extra part of the muscle events present in magnetometers data.')
    else:
        print('___MEG QC___: ', 'No magnetometers or gradiometers found in data. Muscle artifact detection skipped.')
        return [], []

    muscle_derivs=[]

    # Notch filter the data:
    # If line noise is present, you should perform notch-filtering *before*
    #     detecting muscle artifacts. See `tut-section-line-noise` for an example.

    raw.load_data() #need to preloaf data for filtering both in notch filter and in annotate_muscle_zscore
    if (len(powerline_freqs))>0:
        powerline_freqs+=[x*2 for x in powerline_freqs]
        print('___MEG QC___: ', 'Powerline noise found in data. Notch filtering at: ', powerline_freqs, ' Hz')
        raw.notch_filter(powerline_freqs)
    else:
        print('___MEG QC___: ', 'No powerline noise found in data or PSD artifacts detection was not performed. Notch filtering skipped.')


    # The threshold is data dependent, check the optimal threshold by plotting
    # ``scores_muscle``.
    threshold_muscle_list = muscle_params['threshold_muscle']  # z-score
    min_distance_between_different_muscle_events = muscle_params['min_distance_between_different_muscle_events']  # seconds
    
    for m_or_g in m_or_g_decided: #generally no need for loop, we will use just 1 type here. Left n case we change the principle.

        z_scores_dict={}
        for threshold_muscle in threshold_muscle_list:

            z_score_details={}

            annot_muscle, scores_muscle = annotate_muscle_zscore(
            raw, ch_type=m_or_g, threshold=threshold_muscle, min_length_good=0.2,
            filter_freq=[110, 140])

            # ## Plot muscle z-scores across recording
            peak_locs_pos, _ = find_peaks(scores_muscle, height=threshold_muscle, distance=raw.info['sfreq']*min_distance_between_different_muscle_events)

            #print('___MEG QC___: ', 'HERE!', peak_locs_pos)

            muscle_times = raw.times[peak_locs_pos]
            muscle_zscores=scores_muscle[peak_locs_pos]

            fig=go.Figure()
            tit, _ = get_tit_and_unit(m_or_g)
            fig.add_trace(go.Scatter(x=raw.times, y=scores_muscle, mode='lines', name='muscle scores'))
            fig.add_trace(go.Scatter(x=muscle_times, y=muscle_zscores, mode='markers', name='muscle events'))
            fig.add_trace(go.Scatter(x=raw.times, y=[threshold_muscle]*len(raw.times), mode='lines', name='z score threshold: '+str(threshold_muscle)))
            fig.update_layout(xaxis_title='time, (s)', yaxis_title='zscore', title={
            'text': "Muscle z scores over time based on "+tit+". Threshold zscore "+str(threshold_muscle),
            'y':0.85,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'})
            fig.show()

            muscle_derivs += [QC_derivative(fig, 'muscle_z_scores_over_time_based_on_'+tit+'_threshold_zscore_'+str(threshold_muscle), 'plotly')]

            # collect all detailf for simple metric:
            z_score_details['muscle_event_times'] = muscle_times.tolist()
            z_score_details['muscle_event_zscore'] = muscle_zscores.tolist()
            z_scores_dict[threshold_muscle] = {
                'number_muscle_events': len(muscle_times), 
                'Details': z_score_details}
            
            # ## View the annotations (interactive_matplot)
            if interactive_matplot is True:
                order = np.arange(144, 164)
                raw.set_annotations(annot_muscle)
                fig2=raw.plot(start=5, duration=20, order=order)
                #Change settings to show all channels!
            
        simple_metric = make_simple_metric_muscle(m_or_g_decided[0], z_scores_dict)

    return muscle_derivs, simple_metric




