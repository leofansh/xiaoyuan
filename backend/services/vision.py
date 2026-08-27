"""图片理解服务：使用 DeepSeek-V4-Flash-Vision-Exp 识别数学题目照片。"""
import base64
import logging
from typing import Any

logger = logging.getLogger(__name__)

VISION_MODEL = "deepseek-v4-flash-vision-exp"

SYSTEM_PROMPT = """你是一个数学题目图片识别助手。请仔细分析这张数学题目照片，输出以下内容：

1. **文字内容**：照片中所有可读的文字（题目文字、数字、符号等）
2. **数学公式**：用 LaTeX 格式表示所有数学公式
3. **图形描述**：如果照片包含几何图形、函数图像、示意图等，请详细描述：
   - 图形类型（三角形、圆、坐标系等）
   - 标注的点、线、角
   - 给出的已知条件（长度、角度、坐标等）
   - 图形中的数值标注

请用以下 JSON 格式输出：
```json
{
  "text": "照片中的文字内容",
  "formulas": ["LaTeX公式1", "LaTeX公式2"],
  "diagram": {
    "type": "图形类型",
    "description": "详细描述",
    "points": ["标注的点"],
    "given": ["已知条件"]
  }
}
```

如果照片包含题目文字，优先输出完整题目。如果只有图形没有文字，输出图形描述。"""


def recognize_image_sync(image_bytes: bytes, suffix: str = ".jpg") -> dict:
    """使用 DeepSeek-V4-Flash-Vision 识别图片内容。"""
    try:
        from openai import OpenAI
        import os
        
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            return {"available": False, "error": "DEEPSEEK_API_KEY not set"}
        
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        
        # 转换为 base64
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        data_url = f"data:{mime};base64,{b64_image}"
        
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别这张数学题目照片的内容，包括文字、公式和图形。"},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": "high"},
                        },
                    ],
                },
            ],
            max_tokens=1500,
            temperature=0.1,
        )
        
        content = response.choices[0].message.content or ""
        
        # 尝试解析 JSON
        import json
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                result = json.loads(json_match.group())
                return {
                    "available": True,
                    "text": result.get("text", ""),
                    "formulas": result.get("formulas", []),
                    "diagram": result.get("diagram"),
                    "raw": content,
                }
            except json.JSONDecodeError:
                pass
        
        # 降级：返回原始文本
        return {
            "available": True,
            "text": content,
            "formulas": [],
            "diagram": None,
            "raw": content,
        }
        
    except ImportError:
        return {"available": False, "error": "openai package not installed"}
    except Exception as e:
        logger.error("Vision recognition failed: %s", e)
        return {"available": False, "error": str(e)}


async def recognize_image(image_bytes: bytes, suffix: str = ".jpg") -> dict:
    """异步包装。"""
    import asyncio
    return await asyncio.to_thread(recognize_image_sync, image_bytes, suffix)


def describe_for_llm(result: dict, note: str) -> str:
    """把视觉识别结果拼成给小圆看的消息。"""
    parts = ["[学生发来一张题目照片]"]
    
    if result.get("text"):
        parts.append(f"照片内容：\n{result['text']}")
    
    if result.get("formulas"):
        parts.append("识别到的数学公式：")
        for i, f in enumerate(result["formulas"], 1):
            parts.append(f"  公式{i}: ${f}$")
    
    if result.get("diagram"):
        d = result["diagram"]
        parts.append(f"图形信息：")
        parts.append(f"  类型：{d.get('type', '未知')}")
        parts.append(f"  描述：{d.get('description', '')}")
        if d.get("given"):
            parts.append(f"  已知条件：{'；'.join(d['given'])}")
    
    if not result.get("text") and not result.get("formulas") and not result.get("diagram"):
        parts.append("（照片未能清晰识别，请她口头描述题目）")
    
    if note.strip():
        parts.append(f"学生的附言：{note.strip()}")
    
    return "\n".join(parts)
