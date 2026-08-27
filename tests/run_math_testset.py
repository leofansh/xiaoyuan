"""TEST-P1-1 运行器：调用 LLM 解题并用 SymPy 校验正确性。

用法：
  python -m tests.run_math_testset [--limit N] [--domain 代数]
"""
import asyncio
import json
import re
import sys
from typing import Any

import sympy as sp


def extract_numbers(text: str) -> list[str]:
    """从文本中提取所有数字/数值。"""
    # 提取整数、小数、分数（如 3/4）
    return re.findall(r'-?\d+(?:\.\d+)?', text or "")


def eval_expr(expr: str) -> float:
    return float(sp.sympify(expr).evalf())


def verify_case(tc, llm_answer: str) -> tuple[bool, str]:
    """校验 LLM 回答是否正确。返回 (是否通过, 说明)。"""
    kind = tc.verify.get("kind")
    numbers = extract_numbers(llm_answer)
    x = sp.Symbol('x')
    y = sp.Symbol('y')

    if kind == "expression":
        want = eval_expr(tc.verify["expr"])
        # 检查回答中的任一数字是否接近期望值
        for n in numbers:
            if abs(float(n) - want) < 0.01:
                return True, f"答案含 {n}，期望 {want}"
        return False, f"回答 {llm_answer[:40]}... 中无数字接近期望 {want}。提取数字: {numbers}"

    elif kind == "list_contains":
        for want in tc.verify.get("values", []):
            if want in llm_answer:
                return True, f"回答包含 {want}"
        return False, f"回答 {llm_answer[:40]}... 未包含期望值 {tc.verify.get('values')}"

    elif kind == "is_solution_set":
        eq = sp.sympify(tc.verify["eq"])
        want = tc.verify["want"]
        # 解方程（仅作参考）
        try:
            sol = sp.solve(eq, x)
            print(f"  方程 {eq} 的解: {sol}，期望 {want}")
        except Exception:
            sol = []
        # 关键：必须检查 LLM 回答中的数字是否包含正确值
        if any(abs(float(n) - want) < 0.01 for n in numbers):
            return True, f"回答数字接近 {want}"
        return False, f"回答 {llm_answer[:40]}... 未给出 x={want}。提取数字: {numbers}，方程解参考: {sol}"

    elif kind == "is_equation":
        # 解二元一次方程组或判断不等式
        eq1_s = tc.verify.get("eq1", "")
        eq2_s = tc.verify.get("eq2", "")
        # 判断是否含 '>' '<' → 不等式
        if any(op in eq1_s for op in [">", "<", ">=", "<="]):
            # 不等式：检查答案文本格式（一般含 x> 或 x<）
            if '>' in llm_answer or '<' in llm_answer:
                return True, f"回答含不等式符号: {llm_answer[:40]}"
            return False, f"回答 {llm_answer[:40]}... 缺少不等式符号"

        try:
            eq1 = sp.sympify(eq1_s)
            if eq2_s:
                eq2 = sp.sympify(eq2_s)
                sol = sp.solve([eq1, eq2], [x, y], dict=True)
                print(f"  方程组解: {sol}")
                if sol:
                    sx = sol[0].get(x); sy = sol[0].get(y)
                    if sx is not None and sy is not None:
                        hit_x = any(abs(float(n) - float(sx)) < 0.01 for n in numbers)
                        hit_y = any(abs(float(n) - float(sy)) < 0.01 for n in numbers)
                        if hit_x and hit_y:
                            return True, f"回答包含解 x={sx}, y={sy}"
                        return False, f"回答 {llm_answer[:50]}... 需包含 x={sx}, y={sy}。数字: {numbers}"
            else:
                sol = sp.solve(eq1, x)
                print(f"  方程解: {sol}")
                if sol:
                    # 检查回答是否包含任一解
                    for s in sol:
                        try:
                            if abs(float(s) - float(n)) < 0.01:
                                return True, f"回答包含解 x={s}"
                        except (TypeError, ValueError, ZeroDivisionError):
                            continue
                    return False, f"回答 {llm_answer[:50]}... 未包含方程的解 {sol}。数字: {numbers}"
        except Exception as e:
            return False, f"验证异常: {e}"
        return False, f"未能验证。回答: {llm_answer[:50]}"

    return False, f"未知校验方式: {kind}"


async def run_one(tc, client, model: str) -> dict[str, Any]:
    """运行单个测试用例。"""
    system = "你是一名初中数学辅导老师。请只给出最终答案，不要写讲解步骤。如果题目中有方程，直接给出解（如 x=5）。用数字作答。"
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": tc.question},
            ],
            max_tokens=200,
            temperature=0,
        )
        answer = resp.choices[0].message.content or ""
        ok, detail = verify_case(tc, answer)
        return {"id": tc.id, "topic": tc.topic, "domain": tc.domain,
                "question": tc.question, "answer": answer,
                "passed": ok, "detail": detail}
    except Exception as e:
        return {"id": tc.id, "topic": tc.topic, "domain": tc.domain,
                "question": tc.question, "answer": f"调用失败: {e}",
                "passed": False, "detail": f"异常: {e}"}


async def main() -> None:
    from dotenv import load_dotenv, find_dotenv
    import os
    load_dotenv(find_dotenv(usecwd=True)) or load_dotenv(r"D:\PycharmProjects\xiaoyuan\.env")
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        print("缺少 DEEPSEEK_API_KEY")
        sys.exit(1)

    from openai import AsyncOpenAI
    from backend.config import DEEPSEEK_BASE_URL
    from backend.services.calculator import evaluate_expression

    model = os.environ.get("TEST_LLM_MODEL", "deepseek-chat")

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--domain", type=str, default=None)
    args = parser.parse_args()

    from tests.samples.math_testset import TEST_CASES, get_tests_by_domain

    cases = TEST_CASES
    if args.domain:
        cases = get_tests_by_domain().get(args.domain, [])
        print(f"领域「{args.domain}」共 {len(cases)} 题")
    if args.limit:
        cases = cases[:args.limit]
        print(f"本轮测试 {len(cases)} 题")

    client = AsyncOpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL, timeout=60)

    print(f"使用模型: {model}\n")
    passed = failed = 0
    details: list[dict] = []

    # 并发控制：同时跑一批
    BATCH = 4
    for i in range(0, len(cases), BATCH):
        batch = cases[i:i+BATCH]
        results = await asyncio.gather(*[run_one(tc, client, model) for tc in batch])
        for r in results:
            if r["passed"]:
                passed += 1
                mark = "PASS"
            else:
                failed += 1
                mark = "FAIL"
            print(f"[{mark}] {r['id']} [{r['domain']}/{r['topic']}] {r['question'][:30]}...")
            if not r["passed"]:
                print(f"      LLM答: {r['answer'][:100]}")
                print(f"      校验: {r['detail']}")
            details.append(r)

    print(f"\n{'='*50}")
    print(f"通过: {passed} | 失败: {failed} | 总: {len(cases)} | 正确率: {passed}/{len(cases)} = {passed/len(cases)*100:.1f}%")

    # 按领域统计
    from collections import Counter
    by_domain = Counter()
    for r in details:
        by_domain[r["domain"]] += 1
    print("\n领域覆盖:")
    for domain, cnt in sorted(by_domain.items()):
        passed_d = sum(1 for r in details if r["domain"] == domain and r["passed"])
        print(f"  {domain}: {passed_d}/{cnt}")

    # 保存详细结果
    with open("tests/results_math_testset.json", "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "failed": failed, "total": len(cases),
                   "results": details}, f, ensure_ascii=False, indent=2)
    print("\n结果已保存到 tests/results_math_testset.json")


if __name__ == "__main__":
    asyncio.run(main())
