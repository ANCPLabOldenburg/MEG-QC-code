import os
import ancpbids
from ancpbids import load_dataset
import mpld3
import time
import json

from initial_meg_qc import get_all_config_params, sanity_check, initial_processing, detect_extra_channels, detect_noisy_ecg_eog
from RMSE_meq_qc import RMSE_meg_qc
from PSD_meg_qc import PSD_meg_qc
from Peaks_manual_meg_qc import PP_manual_meg_qc
from Peaks_auto_meg_qc import PP_auto_meg_qc
from ECG_meg_qc import ECG_meg_qc
from EOG_meg_qc import EOG_meg_qc
from Head_meg_qc import HEAD_movement_meg_qc
from muscle_meg_qc import MUSCLE_meg_qc
from universal_html_report import make_joined_report, make_joined_report_for_mne
from universal_plots import QC_derivative


def make_derivative_meg_qc(config_file_name):

    """Main function of MEG QC:
    - Parse parameters from config
    - Get the data .fif file for each subject
    - Run whole analysis for every subject, every fif
    - Make and save derivatives (html figures, csvs, html reports)"""

    all_qc_params = get_all_config_params(config_file_name)

    if all_qc_params is None:
        return

    dataset_path = all_qc_params['default']['dataset_path']

    try:
        dataset = ancpbids.load_dataset(dataset_path)
        schema = dataset.get_schema()
    except:
        print('No data found in the given directory path! \nCheck directory path in config file and presence of data on your device.')
        return

    #create derivatives folder first:
    if os.path.isdir(dataset_path+'/derivatives')==False: 
            os.mkdir(dataset_path+'/derivatives')

    derivative = dataset.create_derivative(name="Meg_QC")
    derivative.dataset_description.GeneratedBy.Name = "MEG QC Pipeline"


    # schema = dataset.get_schema()
    # artifacts = filter(lambda m: isinstance(m, schema.Artifact), query(folder, scope=scope))

    # print(schema)
    # print("\n")
    # print(schema.Artifact)

    # print(dataset.files)
    # print(dataset.folders)
    # print(dataset.derivatives)
    # print(dataset.items())
    # print(dataset.keys())
    # print(dataset.code)
    # print(dataset.name)

    #return

    # entities = dataset.query_entities()
    # list_of_subs = list(entities["sub"])
    list_of_subs = sorted(list(dataset.query_entities()["sub"]))
    print('list_of_subs', list_of_subs)

    if not list_of_subs:
        print('No subjects found. Check your data set and directory path in config.')
        return

    for sid in list_of_subs[2:3]: 
        print('Take SID: ', sid)
        
        subject_folder = derivative.create_folder(type_=schema.Subject, name='sub-'+sid)

        list_of_fifs = dataset.query(suffix='meg', extension='.fif', return_type='filename', subj=sid)

        list_of_sub_jsons = dataset.query(sub=sid, suffix='meg', extension='.fif')

        for fif_ind,data_file in enumerate([list_of_fifs[0]]): #RUN OVER JUST 1 fif to save time

            print('Starting initial processing...')
            start_time = time.time()
            dict_of_dfs_epoch, dict_epochs_mg, channels, raw_cropped_filtered, raw_cropped_filtered_resampled, raw_cropped, raw, active_shielding_used = initial_processing(default_settings=all_qc_params['default'], filtering_settings=all_qc_params['Filtering'], epoching_params=all_qc_params['Epoching'], data_file=data_file)
                
            m_or_g_chosen = sanity_check(m_or_g_chosen=all_qc_params['default']['m_or_g_chosen'], channels=channels)
            if len(m_or_g_chosen) == 0: 
                raise ValueError('No channels to analyze. Check presence of mag and grad in your data set and parameter do_for in settings.')
            
            picks_ECG,  picks_EOG = detect_extra_channels(raw)

            # QC measurements:
            rmse_derivs, psd_derivs, pp_manual_derivs, pp_auto_derivs, ecg_derivs, eog_derivs, head_derivs, muscle_derivs, noisy_ecg_derivs, noisy_eog_derivs = [],[],[],[],[], [],  [], [], [], []
            
            simple_metrics_psd, simple_metrics_rmse, simple_metrics_pp_manual, simple_metrics_pp_auto, simple_metrics_ecg, simple_metrics_eog, simple_metrics_head, simple_metrics_muscle = [],[],[],[],[],[], [], []

            df_head_pos = []
            head_not_calculated = False
            bad_ecg=False
            bad_eog=False
            powerline_freqs = None #predefined for the the muscle artif function. If powerline noise is present - need to notch filter it first.
            # For this either need to run psd first, or just guess which powerline freq to use based on the country of the data collection.
            # USA: 60, Europe 50. NOT save to assume powerline noise in every data set. Some really dont have it.

            # noisy_ecg_derivs, bad_ecg=detect_noisy_ecg_eog(raw_cropped, picked_channels_ecg_or_eog=picks_ECG,  thresh_lvl=1.1, plotflag=True)
            # noisy_eog_derivs, bad_eog=detect_noisy_ecg_eog(raw_cropped, picked_channels_ecg_or_eog=picks_EOG,  thresh_lvl=1.1, plotflag=True)

            if bad_ecg is True and picks_ECG is not None: #ecg channel present but noisy - drop it and  try to reconstruct
                no_ecg_str = 'ECG channel data is too noisy, cardio artifacts reconstruction will be attempted but might not be perfect. Cosider checking the quality of ECG channel on your recording device.'
                raw.drop_channels(picks_ECG)
                raw_cropped_filtered.drop_channels(picks_ECG)
                raw_cropped_filtered_resampled.drop_channels(picks_ECG)
                raw_cropped.drop_channels(picks_ECG)

            print("Finished initial processing. --- Execution %s seconds ---" % (time.time() - start_time))
 

            # print('Starting RMSE...')
            # start_time = time.time()
            # rmse_derivs, simple_metrics_rmse = RMSE_meg_qc(all_qc_params['RMSE'], channels, dict_epochs_mg, dict_of_dfs_epoch, raw_cropped_filtered_resampled, m_or_g_chosen)
            # print("Finished RMSE. --- Execution %s seconds ---" % (time.time() - start_time))
 
            # print('Starting PSD...')
            # start_time = time.time()
            # psd_derivs, simple_metrics_psd, powerline_freqs = PSD_meg_qc(all_qc_params['PSD'], channels, raw_cropped_filtered, m_or_g_chosen)
            # print("Finished PSD. --- Execution %s seconds ---" % (time.time() - start_time))

            # print('Starting Peak-to-Peak manual...')
            # start_time = time.time()
            # pp_manual_derivs = PP_manual_meg_qc(all_qc_params['PTP_manual'], channels, dict_epochs_mg, dict_of_dfs_epoch, raw_cropped_filtered_resampled, m_or_g_chosen)
            # print("Finished Peak-to-Peak manual. --- Execution %s seconds ---" % (time.time() - start_time))

            # print('Starting Peak-to-Peak auto...')
            # start_time = time.time()
            # pp_auto_derivs, bad_channels = PP_auto_meg_qc(all_qc_params['PTP_auto'], channels, raw_cropped_filtered_resampled, m_or_g_chosen)
            # print("Finished Peak-to-Peak auto. --- Execution %s seconds ---" % (time.time() - start_time))

            # print('Starting ECG...')
            # start_time = time.time()
            # # Add here!!!: calculate still artif if ch is not present. Check the average peak - if it s reasonable take it.
            # ecg_derivs, simple_metrics_ecg, ecg_events_times, all_ecg_affected_channels = ECG_meg_qc(all_qc_params['ECG'], raw_cropped, channels,  m_or_g_chosen)
            # print("Finished ECG. --- Execution %s seconds ---" % (time.time() - start_time))

            # if picks_EOG is not None and bad_eog is False:
            #     print('Starting EOG...')
            #     start_time = time.time()
            #     eog_derivs, simple_metrics_eog, eog_events_times, all_eog_affected_channels = EOG_meg_qc(all_qc_params['EOG'], raw_cropped, channels,  m_or_g_chosen)
            #     print("Finished EOG. --- Execution %s seconds ---" % (time.time() - start_time))

            # print('Starting Head movement calculation...')
            # head_derivs, simple_metrics_head, head_not_calculated, df_head_pos = HEAD_movement_meg_qc(raw_cropped, plot_with_lines=True, plot_annotations=False)
            # print("Finished Head movement calculation. --- Execution %s seconds ---" % (time.time() - start_time))

            print('Starting Muscle artifacts calculation...')
            #use the same form of raw as in the PSD func! Because psd func calculates first if there are powerline noise freqs.
            muscle_derivs, simple_metrics_muscle = MUSCLE_meg_qc(all_qc_params['Muscle'], raw_cropped_filtered, [60], m_or_g_chosen, interactive_matplot=False)
            print("Finished Muscle artifacts calculation. --- Execution %s seconds ---" % (time.time() - start_time))


            # Make strings with notes for the user to add to html report:
            shielding_str, channels_skipped_str, epoching_skipped_str, no_ecg_str, no_eog_str, no_head_pos_str, no_muscle_str = '', '', '', '', '', '', ''

            if active_shielding_used is True: 
                shielding_str=''' <p>This file contains Internal Active Shielding data. Quality measurements calculated on this data should not be compared to the measuremnts calculated on the data without active shileding, since in the current case invironmental noise reduction was already partially performed by shileding, which normally should not be done before assesing the quality.</p><br></br>'''
            
            if 'mag' not in m_or_g_chosen:
                channels_skipped_str = ''' <p>This data set contains no magnetometers or they were not chosen for analysis. Quality measurements were performed only on gradiometers.</p><br></br>'''
            elif 'grad' not in m_or_g_chosen:
                channels_skipped_str = ''' <p>This data set contains no gradiometers or they were not chosen for analysis. Quality measurements were performed only on magnetometers.</p><br></br>'''

            if dict_of_dfs_epoch['mag'] is None and dict_of_dfs_epoch['grad'] is None:
                epoching_skipped_str = ''' <p>No epoching could be done in this data set: no events found. Quality measurement were only performed on the entire time series. If this was not expected, try: 1) checking the presence of stimulus channel in the data set, 2) setting stimulus channel explicitly in config file, 3) setting different event duration in config file.</p><br></br>'''
            
            if picks_EOG is None:
                no_eog_str = 'No EOG channels found is this data set - EOG artifacts can not be detected.'
                eog_derivs = []

            if head_not_calculated is True:
                no_head_pos_str = 'Head positions can not be computed.'
                head_derivs = []


            QC_derivs={
            'Standard deviation of the data': rmse_derivs, 
            'Frequency spectrum': psd_derivs, 
            'Peak-to-Peak manual': pp_manual_derivs, 
            'Peak-to-Peak auto from MNE': pp_auto_derivs, 
            'ECG': noisy_ecg_derivs+ecg_derivs, 
            'EOG': noisy_eog_derivs+eog_derivs,
            'Head movement artifacts': head_derivs,
            'Muscle artifacts': muscle_derivs}

            QC_simple={
            'Standard deviation of the data': simple_metrics_rmse, 
            'Frequency spectrum': simple_metrics_psd,
            'Peak-to-Peak manual': simple_metrics_pp_manual, 
            'Peak-to-Peak auto from MNE': simple_metrics_pp_auto,
            'ECG': simple_metrics_ecg, 
            'EOG': simple_metrics_eog,
            'Head movement artifacts': simple_metrics_head,
            'Muscle artifacts': simple_metrics_muscle}  


            #Make report and add to QC_derivs:
            report_html_string = make_joined_report(QC_derivs, shielding_str, channels_skipped_str, epoching_skipped_str, no_ecg_str, no_eog_str, no_head_pos_str, no_muscle_str)
            QC_derivs['Report']= [QC_derivative(report_html_string, 'REPORT', 'report')]

            report_html_string = make_joined_report_for_mne(raw, QC_derivs, shielding_str, channels_skipped_str, epoching_skipped_str, no_ecg_str, no_eog_str, no_head_pos_str, no_muscle_str)
            QC_derivs['Report MNE']= [QC_derivative(report_html_string, 'REPORT MNE', 'report mne')]

            #Collect all simple metrics into a dictionary and add to QC_derivs:
            #Add QC_simple to QC_derivs always AFTER the report is made, since the report uses each QC_deriv to make the html string.
            QC_derivs['Simple_metrics']=[QC_derivative(QC_simple, 'Simple_metrics', 'json')]

            #print('HERE!',  QC_derivs)

            # d=0
            for section in QC_derivs.values():
                if section: #if there are any derivs calculated in this section:
                    for deriv in section:
                        
                        # d=d+1
                        # print('writing deriv: ', d)
                        # print(deriv)

                        meg_artifact = subject_folder.create_artifact(raw=list_of_sub_jsons[fif_ind]) #shell. empty derivative
                        meg_artifact.add_entity('desc', deriv.name) #file name
                        meg_artifact.suffix = 'meg'
                        meg_artifact.extension = '.html'

                        if deriv.content_type == 'df':
                            meg_artifact.extension = '.csv'
                            meg_artifact.content = lambda file_path, cont=deriv.content: cont.to_csv(file_path)

                        elif deriv.content_type == 'matplotlib':
                            meg_artifact.content = lambda file_path, cont=deriv.content: mpld3.save_html(cont, file_path)

                        elif deriv.content_type == 'plotly':
                            meg_artifact.content = lambda file_path, cont=deriv.content: cont.write_html(file_path)
  
                        elif deriv.content_type == 'report':
                            def html_writer(file_path, cont=deriv.content):
                                with open(file_path, "w") as file:
                                    file.write(cont)
                                #'with'command doesnt work in lambda
                            meg_artifact.content = html_writer # function pointer instead of lambda

                        elif deriv.content_type == 'report mne':
                            meg_artifact.content = lambda file_path, cont=deriv.content: cont.save(file_path, overwrite=True, open_browser=False)

                        elif deriv.content_type == 'json':
                            meg_artifact.extension = '.json'
                            def json_writer(file_path, cont=deriv.content):
                                with open(file_path, "w") as file_wrapper:
                                    json.dump(cont, file_wrapper, indent=4)
                            meg_artifact.content = json_writer 

                            # with open('derivs.json', 'w') as file_wrapper:
                            #     json.dump(metric, file_wrapper, indent=4)

                        else:
                            print(meg_artifact.name)
                            meg_artifact.content = 'dummy text'
                            meg_artifact.extension = '.txt'
                        # problem with lambda explained:
                        # https://docs.python.org/3/faq/programming.html#why-do-lambdas-defined-in-a-loop-with-different-values-all-return-the-same-result


    ancpbids.write_derivative(dataset, derivative) 

    return raw, QC_derivs, QC_simple, df_head_pos


#%%

# config_file_name = 'settings.ini'
# raw = make_derivative_meg_qc(config_file_name)
