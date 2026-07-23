import sys
import os
import json
import argparse
from typing import Any, List, Tuple, Dict, Literal
from litellm import completion
from litellm.files.main import ModelResponse
from collections import defaultdict
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from constants import EvalLiterals, EvalLLMConfig
from common import BaseRanker, RankingResult, DecodedRankingResult, parse_response_json, decode_ranking


AGENT_LLM_LIST: List[str] = ["qwen3", "kimi2", "claude4", "deepseek", "gpt5", "gemini"]

class MultiAgentRanker(BaseRanker):
    def assemble_response(self, region: Literal["hk", "hb"], category: str, task_ind: int) -> Tuple[str, List[str]]:
        final_response_prefix: str = EvalLiterals.FINAL_RESPONSE_PREFIX
        final_responses: List[str] = []
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
                    
                    final_response: str = log[log.find(final_response_prefix) + len(final_response_prefix):]
                    final_responses.append(final_response)

                    break

        return query, final_responses
    
    def assemble_prompt(self, query: str, responses: List[str]) -> str:

        prompt = "You are an expert environmental science evaluator specializing in air quality analysis, pollution transport modeling, and geospatial data interpretation. Your role is to assess the quality of agent responses to environmental queries with scientific rigor."
        prompt += f"{len(AGENT_LLM_LIST)} geoscience agents have responded to the task: {query}\n"
        prompt += "Their final responses are as follows:\n\n"
        
        for i, llm in enumerate(AGENT_LLM_LIST):
            prompt += f"## Agent {i + 1} Response:\n{responses[i]}\n"
            prompt += "===================================================\n\n"

        prompt += f"""Please rank the {len(AGENT_LLM_LIST)} responses based on the following criteria:

EVALUATION CRITERIA (in order of importance):
1. **Consistency & Plausibility** (40%): Are the results internally consistent, physically plausible, and free from obvious errors? Check for mathematical consistency, reasonable value ranges, and logical coherence.
2. **Completeness** (30%): Does the response fully address all aspects of the user's query? Are all requested analyses present?
3. **Clarity & Organization** (20%): Is the response well-structured and easy to understand? Are findings clearly presented?
4. **Actionable Insights** (10%): Does the response provide useful, actionable findings with appropriate interpretation?

Please return a JSON object with two fields:
- `"ranking"`: a list of response indices, from the best to the worst. For example, [3, 5, 1, 2, 4] means the best response is the 3rd one, the 5th one is the second best, and so on.
- `"reason"`: a brief explanation for why the ranking was given.

JSON:
"""
        return prompt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", type=str, required=True, choices=["hk", "hb"])
    parser.add_argument("--category", type=str, required=True, choices=["cat_1", "cat_2", "cat_3", "cat_4", "cat_5", "cat_6", "cat_7"])

    return parser.parse_args()

def main():
    args = parse_args()
    region: str = args.region
    category: str = args.category

    ranker: BaseRanker = MultiAgentRanker()

    log_dir_path: str = f"./logs_to_eval/{region}/claude4/{EvalLiterals.CATEGORY_LIBRARY[category]}"
    n_tasks: int = len(os.listdir(log_dir_path))

    start_task_ind: int = 1

    ranking_results_path: str = f"./eval_results/ranking/{region}/{region}_{category}_judge_claude4_ranking_results.json"
    if not os.path.exists(ranking_results_path):
        ranking_results: List[DecodedRankingResult] = []
    else:
        ranking_results: List[DecodedRankingResult] = json.load(open(ranking_results_path, "r"))
        ranking_results = [DecodedRankingResult(**result) for result in ranking_results]
        start_task_ind = len(ranking_results) + 1

    print(f"Processing {n_tasks} tasks...")

    for task_ind in range(start_task_ind, n_tasks + 1):
        print(f">>> Ranking agent responses for task {task_ind} / {n_tasks}...")
        query, final_responses = ranker.assemble_response(region, category, task_ind)
        prompt = ranker.assemble_prompt(query, final_responses)

        messages: List[Dict[str, str]] = [
            {
                "content": prompt,
                "role": "user"
            }
        ]

        response: ModelResponse = completion(
            model="claude-sonnet-4-20250514",
            api_key=EvalLLMConfig.OPENAI_HK_API_KEY,
            base_url="https://api.openai-hk.com/",
            messages=messages,
            temperature=0.0
        )

        response_content = response.choices[0].message.content
        ranking_result: RankingResult = parse_response_json(response_content)

        decoded_ranking: Dict[str, int] = decode_ranking(ranking_result.ranking, AGENT_LLM_LIST)

        decoded_ranking_result = DecodedRankingResult(
            ranking=decoded_ranking,
            reason=ranking_result.reason
        )

        print(decoded_ranking_result.ranking)

        ranking_results.append(decoded_ranking_result)

        with open(ranking_results_path, "w") as f:
            json.dump([result.model_dump() for result in ranking_results], f, indent=4)


if __name__ == "__main__":
    main()
