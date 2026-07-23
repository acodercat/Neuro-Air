import sys
import os
import json
import argparse
from typing import List, Tuple, Literal, Dict
from deepeval import compare
from litellm import completion, ModelResponse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import EvalLiterals, EvalLLMConfig
from common import BaseRanker, RankingResult, DecodedRankingResult, parse_response_json, decode_ranking


AGENT_LLM_LIST: List[str] = ["claude4", "control_group_2"]

class CompareRanker(BaseRanker):
    def assemble_response(self, region: Literal["hk", "hb"], category: str, task_ind: int) -> Tuple[str, List[str]]:
        trajectories: List[str] = []
        query: str = None

        for llm in AGENT_LLM_LIST:
            log_dir_path: str = f"./logs_to_eval/{region}/{llm}/{EvalLiterals.CATEGORY_LIBRARY[category]}"
            log_file_prefix: str = f"{category[4]}-{str(task_ind)}_"
            
            for file in os.listdir(log_dir_path):
                if file.startswith(log_file_prefix):
                    log_file_path: str = os.path.join(log_dir_path, file)
                
                    with open(log_file_path, "r") as f:
                        first_line = f.readline().strip()
                        if not query and first_line.startswith(EvalLiterals.USER_QUERY_PREFIX):
                            query = first_line[len(EvalLiterals.USER_QUERY_PREFIX):]

                        log: str = f.read()

                    trajectories.append(log)

                    break

        return query, trajectories

    def assemble_prompt(self, query: str, final_responses: List[str]) -> str:
        prompt = "You are an expert environmental science evaluator specializing in air quality analysis and geospatial analysis. Your role is to assess the quality of agent responses to environmental queries with scientific rigor."
        prompt += f"\nTwo geoscience agents have responded to the task: {query}\n"
        prompt += "Their complete task-solving trajectories are as follows:\n\n"
        
        for i, llm in enumerate(AGENT_LLM_LIST):
            prompt += f"## Agent {i + 1} Task-solving Trajectory:\n\n{final_responses[i]}\n"
            prompt += "===================================================\n\n"
        
        prompt += """EVALUATION CRITERIA (in order of importance):
    1. **Consistency & Plausibility** (30%): Are the results internally consistent, physically plausible, and free from obvious errors? Check for mathematical consistency, reasonable value ranges, and logical coherence.
    2. **Completeness** (25%): Does the response fully address all aspects of the user's query? Are all requested analyses present?
    3. **Technical Methodology** (25%): Technical Methodology: Which agent showed greater analytical sophistication and adaptability?
    4. **Clarity & Organization** (15%): Is the response well-structured and easy to understand? Are findings clearly presented?
    5. **Actionable Insights** (5%): Does the response provide useful, actionable findings with appropriate interpretation?

    Please return a JSON object with two fields:
    - `"ranking"`: a list of trajectory indices from best to worst. Example: [1, 2] means Agent 1 is better than Agent 2
    - `"reason"`: a brief explanation comparing both trajectories, highlighting specific strengths and weaknesses, methodology differences, and justification for the ranking

    JSON:"""
        
        return prompt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", type=str, required=True, choices=["cat_1", "cat_2", "cat_3", "cat_4", "cat_5", "cat_6"])

    return parser.parse_args()

def main():
    args = parse_args()

    category: str = args.category
    region: str = "hk"
    
    ranker: BaseRanker = CompareRanker()

    log_dir_path: str = f"./logs_to_eval/{region}/claude4/{EvalLiterals.CATEGORY_LIBRARY[category]}"
    n_tasks: int = len(os.listdir(log_dir_path))

    start_task_ind: int = 1

    compare_results_path: str = f"./eval_results/compare/{region}/{region}_{category}_judge_claude4_compare_results.json"
    if not os.path.exists(compare_results_path):
        compare_results: List[DecodedRankingResult] = []
    else:
        compare_results: List[DecodedRankingResult] = json.load(open(compare_results_path, "r"))
        compare_results = [DecodedRankingResult(**result) for result in compare_results]
        start_task_ind = len(compare_results) + 1

    print(f"Processing {n_tasks} tasks...")

    for task_ind in range(start_task_ind, n_tasks + 1):
        print(f">>> Comparing agent responses for task {task_ind} / {n_tasks}...")
        query, responses = ranker.assemble_response(region, category, task_ind)
        prompt = ranker.assemble_prompt(query, responses)

        messages: List[Dict[str, str]] = [
            {
                "content": prompt,
                "role": "user"
            }
        ]

        response: ModelResponse = completion(
            model="claude-sonnet-4-20250514",
            api_key=EvalLLMConfig.ANTHROPIC_API_KEY,
            temperature=0.0,
            messages=messages
        )

        response_content = response.choices[0].message.content
        compare_result: RankingResult = parse_response_json(response_content)

        decoded_ranking: Dict[str, int] = decode_ranking(compare_result.ranking, AGENT_LLM_LIST)

        decoded_ranking_result = DecodedRankingResult(
            ranking=decoded_ranking,
            reason=compare_result.reason
        )

        print(decoded_ranking_result.ranking)

        compare_results.append(decoded_ranking_result)

        with open(compare_results_path, "w") as f:
            json.dump([result.model_dump() for result in compare_results], f, indent=4)
    

if __name__ == "__main__":
    main()
