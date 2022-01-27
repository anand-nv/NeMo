work_dir=/media/apeganov/DATA/punctuation_and_capitalization/all_punc_no_u/3_128/wiki_wmt_18.01.2022
output_dir="${work_dir}/inference_on_IWSLT_tst2019_results"
model_name=all_punc_no_u_nmt_wiki_wmt_news_crawl_large6x6_bs400000_steps400000_lr2e-4
python compute_metrics.py \
  --hyp "${output_dir}/${model_name}_with_adjustment_labels.txt" \
  --ref "${work_dir}/for_upload/IWSLT_tst2019/autoregressive_labels.txt" \
  --output "${output_dir}/${model_name}_with_adjustment_scores.json"