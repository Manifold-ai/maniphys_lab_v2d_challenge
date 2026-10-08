# command  : bash -c ssh\ -o\ BatchMode=yes\ mf4090\ \"cd\ /home/rxzhou/v2d/maniphys_lab_v2d_challenge\ \&\&\ md5sum\ runs/tools/hf_archive.py\ runs/tools/hf_archive_run.sh\ runs/tools/test_hf_archive.py\ \&\&\ python3\ runs/tools/test_hf_archive.py\" 
# source   : 10465fd28035-dirty
# host     : Rongxuans-MacBook-Air.local
# run_at   : 2026-10-08T11:07:19-0600
# ---------------------------------------------------------------
a7f6ce8272e482a5b0f3449f0d55bb89  runs/tools/hf_archive.py
9663a9f6156cd98203a14320d8d5e6a1  runs/tools/hf_archive_run.sh
751c5dd3989be99281354e57ad1762b4  runs/tools/test_hf_archive.py
ok test_plan_rules
ok test_delete_gates_and_effects
ok test_rerun_after_interrupted_delete_writes_state_pruned
ok test_policy_plan_rules
ok test_policy_delete
ok test_policy_delete_skips_run_whose_newest_policy_broke
ok test_export_input_lists_protect
ok test_spot_pick
ok test_readme_and_upload_guard
ok test_runner_verify_step
ok test_runner_delete_step
ok test_runner_files_check_catches_extra_deletion
ALL_OK
