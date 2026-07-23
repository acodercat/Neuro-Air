import os
import sys
from unicodedata import category

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking import assemble_final_response, AGENT_LLM_LIST

def main():
    region: str = "hk"
    category: str = "cat_1"
    task_ind: int = 9

    query, final_responses = assemble_final_response(region, category, task_ind)

    print(query, "\n\n")
    for i, response in enumerate(final_responses):
        print(f"{AGENT_LLM_LIST[i]}: {response}")
        print("\n==============================================\n")


if __name__ == "__main__":
    main()