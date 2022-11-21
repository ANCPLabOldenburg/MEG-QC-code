# Calculating peak-to-peak amplitudes using mne annotations.

# !!! Automatically choose peak and flat values by averaging the data maybe?

import pandas as pd
import mne
from universal_plots import QC_derivative

def get_amplitude_annots_per_channel(raw: mne.io.Raw, peak: float, flat: float, channels: list, bad_percent:  int, min_duration: float) -> tuple[pd.DataFrame, list]:
    """Function creates amplitude (peak-to-peak annotations) for every channel separately"""
    
    amplit_annot_with_ch_names=mne.Annotations(onset=[], duration=[], description=[], orig_time=raw.annotations.orig_time) #initialize 
    bad_channels=[]

    for channel in channels:
        #get annotation object:
        amplit_annot=mne.preprocessing.annotate_amplitude(raw, peak=peak, flat=flat , bad_percent=bad_percent, min_duration=min_duration, picks=[channel], verbose=False)
        bad_channels.append(amplit_annot[1]) #Can later add these into annotation as well.

        if len(amplit_annot[0])>0:
            #create new annot obj and add there all data + channel name:
            amplit_annot_with_ch_names.append(onset=amplit_annot[0][0]['onset'], duration=amplit_annot[0][0]['duration'], description=amplit_annot[0][0]['description'], ch_names=[[channel]])

    df_ptp_amlitude_annot=amplit_annot_with_ch_names.to_data_frame()
    return df_ptp_amlitude_annot, bad_channels


def PP_auto_meg_qc(ptp_auto_params: dict, channels:list, data: mne.io.Raw, m_or_g_chosen: list):

    peaks = {'grads': ptp_auto_params['peak_g'], 'mags': ptp_auto_params['peak_m']}
    flats = {'grads': ptp_auto_params['flat_g'], 'mags': ptp_auto_params['flat_m']}
    bad_channels = {}

    deriv_ptp_auto= []
    for  m_or_g in m_or_g_chosen:
        dfs_ptp_amlitude_annot, bad_channels[m_or_g] = get_amplitude_annots_per_channel(data, peaks[m_or_g], flats[m_or_g], channels[m_or_g], bad_percent=ptp_auto_params['bad_percent'], min_duration= ptp_auto_params['min_duration'])
        deriv_ptp_auto += [QC_derivative(dfs_ptp_amlitude_annot,'ptp_amplitude_annots_'+m_or_g, None, 'df')]

    return deriv_ptp_auto, bad_channels
