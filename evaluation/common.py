import os
import json
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, List, Literal, Tuple, Any, Union

class RankingResult(BaseModel):
    ranking: List[int]
    reason: str

class DecodedRankingResult(BaseModel):
    ranking: Dict[str, int]
    reason: str


class BaseRanker(ABC):

    @abstractmethod
    def assemble_response(self, region: Literal["hk", "hb"], category: str, task_ind: int) -> Tuple[str, List[str]]:
        pass

    @abstractmethod
    def assemble_prompt(self, query: str, responses: List[str]) -> str:
        pass

def parse_response_json(response: str) -> RankingResult:
    start = response.find("{")
    end = response.rfind("}") + 1
    json_str = response[start:end]

    ranking_result = RankingResult(**json.loads(json_str))
    
    return ranking_result

def decode_ranking(ranking: List[int], agent_llm_list: List[str]) -> Dict[str, Any]:
    decoded_ranking: Dict[str, Any] = {}
    for i, rank in enumerate(ranking):
        decoded_ranking[agent_llm_list[rank - 1]] = i + 1

    return decoded_ranking


def _process_ranking_files(directory_path: str, category: Union[str, None] = None) -> (int, Dict[str, int]):
    """
    Reads all JSON files in a directory, processes the ranking results,
    and returns the task count and a dictionary of summed ranks for each LLM.
    """
    task_count = 0
    summed_ranks = {}
    if not os.path.exists(directory_path):
        print(f"Warning: Directory not found at {directory_path}")
        return 0, {}

    for file in os.listdir(directory_path):
        if category and category not in file:
            continue
        path = os.path.join(directory_path, file)
        if os.path.isfile(path) and file.endswith('.json'):
            with open(path, "r") as f:
                try:
                    ranking_results: List[Dict] = json.load(f)
                    ranking_results = [DecodedRankingResult(**result) for result in ranking_results]
                    task_count += len(ranking_results)

                    for result in ranking_results:
                        for llm, rank in result.ranking.items():
                            summed_ranks[llm] = summed_ranks.get(llm, 0) + rank
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error processing file {path}: {e}")

    return task_count, summed_ranks


def analyze_ranking_results(
    region: Literal["hk", "hb", "all"], 
    category: Union[Literal["cat_1", "cat_2", "cat_3", "cat_4", "cat_5", "cat_6", "cat_7"], None] = None
    ):
    """
    Analyzes ranking results from specified region(s) and prints the average ranking for each LLM.
    """
    # region_dir_map: Dict[str, str] = {
    #     "hk": "./eval_results/ranking/hk",
    #     "hb": "./eval_results/ranking/hb",
    # }

    region_dir_map: Dict[str, str] = {
        "hk": "./eval_results/compare/hk",
        "hb": "./eval_results/compare/hb",
    }

    total_task_count: int = 0
    total_average_ranking: Dict[str, float] = {}

    regions_to_process = []
    if region == "all":
        regions_to_process = list(region_dir_map.keys())
    elif region in region_dir_map:
        regions_to_process = [region]

    for reg in regions_to_process:
        dir_path = region_dir_map[reg]
        task_count, summed_ranks = _process_ranking_files(dir_path, category)
        total_task_count += task_count
        for llm, rank_sum in summed_ranks.items():
            total_average_ranking[llm] = total_average_ranking.get(llm, 0) + rank_sum

    print(total_average_ranking)
    print(task_count)

    if total_task_count > 0:
        for llm, rank_sum in total_average_ranking.items():
            total_average_ranking[llm] = rank_sum / total_task_count

    print(total_average_ranking)

if __name__ == "__main__":
    analyze_ranking_results(region="hk", category="cat_6")