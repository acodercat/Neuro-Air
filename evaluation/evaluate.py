import os
import json
import sys
import argparse
import time
from typing import List, Dict, Union
from pydantic import BaseModel
from deepeval import evaluate
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams
from deepeval.test_case import LLMTestCase
from deepeval.models.llms import LiteLLMModel, LocalModel
from deepeval.evaluate.types import EvaluationResult
from deepeval.evaluate.configs import AsyncConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import EvalLiterals, get_judge_llm

class MetricResult(BaseModel):
    metric_name: str
    score: float
    reason: str

class CaseEvalResult(BaseModel):
    input: str
    actual_output: str
    metrics: List[MetricResult]

class EvalResult(BaseModel):
    statistics: Dict[str, float]
    case_eval_results: List[CaseEvalResult]

class Evaluator:
    def __init__(self, judge_llm: str, concurrency: int = 1):
        judge_model: Union[LocalModel, LiteLLMModel] = get_judge_llm(judge_llm)
        self.metrics: List[GEval] = [
            GEval(
                name=metric.name,
                criteria=metric.criteria,
                evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
                model=judge_model
            ) for metric in EvalLiterals.METRIC_LIBRARY
        ]

        if concurrency > 1:
            self.async_config = AsyncConfig(
                run_async=True,
                max_concurrent=concurrency
            )
        else:
            self.async_config = AsyncConfig(
                run_async=False
            )
    
    def parallel_evaluate(self, test_cases: List[LLMTestCase]) -> EvalResult:
        raw_results: EvaluationResult = evaluate(
            test_cases=test_cases, 
            metrics=self.metrics,
            async_config=self.async_config
        )
        return self._assemble_results(raw_results)
    
    @staticmethod
    def _parse_results(raw_results: EvaluationResult) -> List[CaseEvalResult]:
        """Parse the raw results returned by deepeval.evaluate() into a list of CaseEvalResult"""
        parsed_results: List[CaseEvalResult] = []
        for test_result in raw_results.test_results:
            parsed_results.append(
                CaseEvalResult(
                    input=test_result.input,
                    actual_output=test_result.actual_output,
                    metrics=[
                        MetricResult(
                            metric_name=metric.name,
                            score=metric.score,
                            reason=metric.reason
                        ) for metric in test_result.metrics_data
                    ]
                )
            )

        return parsed_results
    
    @staticmethod
    def _assemble_results(raw_results: EvaluationResult) -> EvalResult:
        """Assemble the raw results returned by deepeval.evaluate() into a EvalResult"""
        case_eval_results: List[CaseEvalResult] = Evaluator._parse_results(raw_results)
        statistics: Dict[str, float] = {}
        for metric in EvalLiterals.METRIC_LIBRARY:
            statistics[metric.name] = Evaluator.compute_metric_mean(case_eval_results, metric.name)
        return EvalResult(
            statistics=statistics,
            case_eval_results=case_eval_results
        )
    
    @staticmethod
    def compute_metric_mean(results: List[CaseEvalResult], metric_name: str) -> float:
        """Compute the mean score of a given metric across all test case eval results"""
        sum_score: float = 0.0
        for result in results:
            for metric in result.metrics:
                if metric.metric_name.lower().startswith(metric_name.lower()):
                    sum_score += metric.score
                    break
        return sum_score / len(results)

    def sequential_evaluate(self, test_cases: List[LLMTestCase], eval_log_path: str, retry: int = 1) -> EvalResult:
        """Evaluate the test case sequentially"""
        start_ind: int = 0
        if not os.path.exists(eval_log_path):
            case_eval_results: List[CaseEvalResult] = []
        else:
            # Load the previous results from the checkpoint
            with open(eval_log_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
                case_eval_results: List[CaseEvalResult] = [CaseEvalResult(**item) for item in raw_json]
            start_ind = len(case_eval_results)

        for i, test_case in enumerate(test_cases):
            if i < start_ind:
                continue

            print(f">>> Evaluating test case {i + 1} / {len(test_cases)}")

            for attempt in range(retry):
                try:
                    metric_results: List[MetricResult] = []
                    for metric in self.metrics:
                        metric.measure(test_case=test_case)
                        metric_result = MetricResult(
                            metric_name=metric.name,
                            score=metric.score,
                            reason=metric.reason
                        )
                        metric_results.append(metric_result)
                    break
                except Exception as e:
                    if attempt == retry - 1:
                        raise e
                    else:
                        time.sleep(3)
                        continue

            case_eval_result = CaseEvalResult(
                input=test_case.input,
                actual_output=test_case.actual_output,
                metrics=metric_results
            )
            case_eval_results.append(case_eval_result)
            
            # Save the current results as a checkpoint
            with open(eval_log_path, "w", encoding="utf-8") as f:
                result_json = [case_eval_result.model_dump() for case_eval_result in case_eval_results]
                json.dump(result_json, f, indent=4)
                print(f"Saved checkpoint to {eval_log_path}")

            time.sleep(5)

        statistics: Dict[str, float] = {}
        for metric in EvalLiterals.METRIC_LIBRARY:
            statistics[metric.name] = Evaluator.compute_metric_mean(case_eval_results, metric.name)
        return EvalResult(
            statistics=statistics,
            case_eval_results=case_eval_results
        )        

    
AGENT_LIST = ["claude4", "kimi2", "gpt5", "deepseek", "gemini", "qwen3", "control_group_1", "control_group_2"]
JUDGE_LIST = ["claude4", "kimi2", "gpt5", "deepseek", "gemini", "qwen3"]
CATEGORY_LIST = ["cat_1", "cat_2", "cat_3", "cat_4", "cat_5", "cat_6", "cat_7", "cat_8"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent_llm", type=str, choices=AGENT_LIST, required=True)
    parser.add_argument("--category", type=str, choices=CATEGORY_LIST, required=True)
    parser.add_argument("--judge_llm", type=str, choices=JUDGE_LIST, required=True)
    parser.add_argument("--region", type=str, choices=["hk", "hb"], required=True)
    parser.add_argument("--concurrency", type=int, default=2, required=True)
    parser.add_argument("--retry", type=int, default=2)

    return parser.parse_args()

def main():
    args = parse_args()

    agent_llm: str = args.agent_llm
    category: str = args.category
    judge_llm: str = args.judge_llm
    concurrency: int = args.concurrency
    retry: int = args.retry
    region: str = args.region

    test_cases: List[LLMTestCase] = []

    case_log_dir: str = f"./logs_to_eval/{region}/{agent_llm}/{EvalLiterals.CATEGORY_LIBRARY[category]}"

    for dir_path, dir_names, file_names in os.walk(case_log_dir):
        # Sort directories and files to ensure a deterministic order
        dir_names.sort()
        file_names.sort()
        
        for file_name in file_names:

            with open(os.path.join(dir_path, file_name), "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith(EvalLiterals.USER_QUERY_PREFIX):
                    case_input = first_line[len(EvalLiterals.USER_QUERY_PREFIX):]
                
                case_output = f.read() # The remaining lines are the agent output

            test_cases.append(
                LLMTestCase(
                    input=case_input,
                    actual_output=case_output,
                    expected_output="",
                    context=[EvalLiterals.AGENT_CONTEXT_SUMMARY],
                )
            )
    
    evaluator = Evaluator(judge_llm=judge_llm, concurrency=concurrency)
    result_save_path: str = f"./eval_results/{region}/{agent_llm}/{region}_{category}_agent_{agent_llm}_judge_{judge_llm}_eval_results.json"

    if concurrency > 1:
        results: EvalResult = evaluator.parallel_evaluate(test_cases)
    else:
        results: EvalResult = evaluator.sequential_evaluate(test_cases, result_save_path, retry=retry)

    result_json = results.model_dump_json(indent=4)
    with open(result_save_path, "w", encoding="utf-8") as f:
        f.write(result_json)

if __name__ == "__main__":
    main()

