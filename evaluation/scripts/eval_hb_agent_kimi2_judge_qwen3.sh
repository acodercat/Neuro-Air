#!/bin/bash

AGENT_LLM="kimi2"
JUDGE_LLM="qwen3"
CONCURRENCY=1
RETRY=4
REGION="hb"

CATEGORIES=("cat_1" "cat_2" "cat_3" "cat_4" "cat_5" "cat_6" "cat_7")
# CATEGORIES=("cat_4" "cat_5" "cat_6" "cat_7")

for category in "${CATEGORIES[@]}"; do
    echo "Evaluating category: $category"
    uv run evaluate.py \
        --agent_llm "$AGENT_LLM" \
        --judge_llm "$JUDGE_LLM" \
        --category "$category" \
        --concurrency "$CONCURRENCY" \
        --retry "$RETRY" \
        --region "$REGION"
    
    if [ $? -eq 0 ]; then
        echo "✅ Category $category evaluation completed"
    else
        echo "❌ Category $category evaluation failed"
        exit 1
    fi
done
