import os
import sys
import argparse
import json
from typing import Dict, List, Any, Literal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import EvalLiterals
from evaluate import EvalResult, CaseEvalResult, MetricResult


HK_TASK_COUNT: Dict[str, int] = {
    "cat_1": 13,
    "cat_2": 19,
    "cat_3": 18,
    "cat_4": 31,
    "cat_5": 14,
    "cat_6": 22
}

HB_TASK_COUNT: Dict[str, int] = {
    "cat_1": 43,
    "cat_2": 36,
    "cat_3": 28,
    "cat_4": 10,
    "cat_5": 29,
    "cat_6": 17,
    "cat_7": 37
}

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", type=str, required=True, choices=["hk", "hb"])
    parser.add_argument("--agent_llm", type=str, required=True, choices=["gpt5", "claude4", "gemini"])
    parser.add_argument("--criteria", type=str.upper, required=True, choices=["MS", "TIQ", "DIS", "RA", "FAI", "OVERALL"])
    return parser.parse_args()


def compute_metric_mean(
    region: str, 
    task_ind: int, 
    agent_llm: str,
    category: Literal["cat_1", "cat_2", "cat_3", "cat_4", "cat_5", "cat_6", "cat_7"],
    metric: Literal["MS", "TIQ", "DIS", "RA", "FAI"]
    ) -> float:

    eval_result_folderdir: str = f"./eval_results/{region}/{agent_llm}"
    prefix = f"{region}_{category}_agent_{agent_llm}"

    judge_llm_list: List[str] = ["claude4", "kimi2", "qwen3"]
    metric_mapping: Dict[str, str] = EvalLiterals.CRITERIA_MAPPING

    scores: List[float] = []

    for judge_llm in judge_llm_list:
        eval_log_dir = eval_result_folderdir + f"/{prefix}_judge_{judge_llm}_eval_results.json"
        with open(eval_log_dir, "r") as f:
            eval_result = json.load(f)
        eval_result = EvalResult(**eval_result)
        case_eval_result: CaseEvalResult = eval_result.case_eval_results[task_ind - 1]
        metric_results: List[MetricResult] = case_eval_result.metrics
        for metric_result in metric_results:
            if metric_result.metric_name.lower().startswith(metric_mapping[metric].lower()):
                scores.append(metric_result.score)
                break
    
    return sum(scores) / len(scores)

def divide_into_bins(scores: List[float]) -> Dict[str:, int]:
    bins: Dict[str, int] = {
        "<0.8": 0,
        "0.8-0.85": 0,
        "0.85-0.9": 0,
        "0.9-0.95": 0,
        "0.95-1.0": 0,
    }

    for score in scores:
        if score < 0.8:
            bins["<0.8"] += 1
        elif score < 0.85:
            bins["0.8-0.85"] += 1
        elif score < 0.9:
            bins["0.85-0.9"] += 1
        elif score < 0.95:
            bins["0.9-0.95"] += 1
        else:
            bins["0.95-1.0"] += 1
    return bins

def main():
    args = parse_args()

    region: str = args.region
    agent_llm: str = args.agent_llm
    criteria_abbr: str = args.criteria

    if region == "hk":
        category_list = HK_TASK_COUNT.keys()
        task_count_mapping = HK_TASK_COUNT
    elif region == "hb":
        category_list = HB_TASK_COUNT.keys()
        task_count_mapping = HB_TASK_COUNT

    if criteria_abbr != "OVERALL":
        scores: List[float] = []
        for category in category_list:
            for task_ind in range(1, task_count_mapping[category] + 1):
                scores.append(
                    compute_metric_mean(
                        region=region,
                        task_ind=task_ind,
                        agent_llm=agent_llm,
                        category=category,
                        metric=criteria_abbr
                    )
                )
    else:
        scores: List[float] = []
        for category in category_list:
            for task_ind in range(1, task_count_mapping[category] + 1):
                _scores: List[float] = []
                for metric in EvalLiterals.CRITERIA_MAPPING.keys():
                    _scores.append(
                        compute_metric_mean(
                            region=region,
                            task_ind=task_ind,
                            agent_llm=agent_llm,
                            category=category,
                            metric=metric
                        )
                    )
                scores.append(sum(_scores) / len(_scores))

    bins = divide_into_bins(scores)
    print(bins)


if __name__ == "__main__":
    main()