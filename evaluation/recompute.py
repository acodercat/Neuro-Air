import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluate import Evaluator, EvalResult
from constants import EvalLiterals

if __name__ == "__main__":
    agent_llm: str = "qwen3"
    region: str = "hk"
    category: str = "cat_4"
    judge_llm: str = "qwen3"

    eval_log_path: str = f"./eval_results/{region}/{agent_llm}/{region}_{category}_agent_{agent_llm}_judge_{judge_llm}_eval_results.json"

    with open(eval_log_path, "r") as f:
        eval_results = json.load(f)

    eval_results = EvalResult(**eval_results)

    old_statistics = eval_results.statistics
    case_eval_results = eval_results.case_eval_results
    
    statistics = {}
    for metric in EvalLiterals.METRIC_LIBRARY:
        statistics[metric.name] = Evaluator.compute_metric_mean(case_eval_results, metric.name)

    eval_results.statistics = statistics

    print(old_statistics)
    print(statistics)

    with open(eval_log_path, "w") as f:
        json.dump(eval_results.model_dump(), f, indent=4)

    