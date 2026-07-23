import os
import sys
import argparse
import json
from typing import Dict, List, Any, Literal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evaluate import EvalResult, CaseEvalResult, MetricResult
from freq_count_by_metric import HK_TASK_COUNT, HB_TASK_COUNT, divide_into_bins


def compute_category_mean(
    region: str, 
    task_ind: int, 
    agent_llm: str,
    category: Literal["cat_1", "cat_2", "cat_3", "cat_4", "cat_5", "cat_6", "cat_7"],
    ) -> float:

    eval_result_folderdir: str = f"./eval_results/{region}/{agent_llm}"
    prefix = f"{region}_{category}_agent_{agent_llm}"

    judge_llm_list: List[str] = ["claude4", "kimi2", "qwen3"]

    scores: List[float] = []

    for judge_llm in judge_llm_list:
        eval_log_dir = eval_result_folderdir + f"/{prefix}_judge_{judge_llm}_eval_results.json"
        with open(eval_log_dir, "r") as f:
            eval_result = json.load(f)
        eval_result = EvalResult(**eval_result)
        case_eval_result: CaseEvalResult = eval_result.case_eval_results[task_ind - 1]
        metric_results: List[MetricResult] = case_eval_result.metrics

        _scores: List[float] = []

        for metric_result in metric_results:
            _scores.append(metric_result.score)

        scores.append(sum(_scores) / len(_scores))
    
    return sum(scores) / len(scores)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", type=str, required=True, choices=["hk", "hb"])
    parser.add_argument("--agent_llm", type=str, required=True, choices=["gpt5", "claude4", "gemini"])
    parser.add_argument("--category", type=str, required=True, choices=["cat_1", "cat_2", "cat_3", "cat_4", "cat_5", "cat_6"])
    return parser.parse_args()


def main():
    args = parse_args()
    region = args.region
    agent_llm = args.agent_llm
    category = args.category

    if region == "hk":
        task_count_mapping = HK_TASK_COUNT
    elif region == "hb":
        task_count_mapping = HB_TASK_COUNT


    if region == "hb" and category == "cat_2":
        scores: List[float] = []
        for task_ind in range(1, task_count_mapping["cat_2"] + 1):
            score = compute_category_mean(
                region=region,
                task_ind=task_ind,
                agent_llm=agent_llm,
                category="cat_2"
            )
            scores.append(score)
        for task_ind in range(1, task_count_mapping["cat_7"] + 1):
            score = compute_category_mean(
                region=region,
                task_ind=task_ind,
                agent_llm=agent_llm,
                category="cat_7"
            )
            scores.append(score)

    else:
        scores: List[float] = []
        for task_ind in range(1, task_count_mapping[category] + 1):
            score = compute_category_mean(
                region=region,
                task_ind=task_ind,
                agent_llm=agent_llm,
                category=category
            )
            scores.append(score)
    
    print(divide_into_bins(scores=scores))


if __name__ == "__main__":
    main()