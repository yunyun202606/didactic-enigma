"""身份证/户口本 OCR 信息提取
支持从身份证或户口本图片中提取: 姓名、身份证号码、性别、村小组
"""
from __future__ import annotations
import re
import json
from pathlib import Path
from typing import Dict, Optional, List, Tuple


def _has_paddle() -> bool:
    try:
        import paddleocr  # noqa: F401
        import paddle  # noqa: F401
        return True
    except Exception:
        return False


def _has_tesseract() -> bool:
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _default_engine() -> str:
    if _has_paddle():
        return "paddle"
    if _has_tesseract():
        return "tesseract"
    return "paddle"


class IDCardOCR:
    """身份证/户口本 OCR 识别器"""

    def __init__(self, engine: str = "auto"):
        if engine == "auto":
            engine = _default_engine()
        self.engine = engine
        self._ocr = None

    def _init_ocr(self):
        if self._ocr is not None:
            return
        if self.engine == "paddle":
            try:
                from paddleocr import PaddleOCR
                self._ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",
                    show_log=False,
                )
            except ImportError:
                if _has_tesseract():
                    self.engine = "tesseract"
                    return self._init_ocr()
                raise ImportError(
                    "PaddleOCR 未安装, 请运行: pip install paddleocr paddlepaddle "
                    "(需要 Python 3.7~3.11, 当前 Python 不支持时可使用 Tesseract)"
                )
        elif self.engine == "tesseract":
            try:
                import pytesseract
                from PIL import Image
                self._ocr = pytesseract
                self._Image = Image
            except ImportError:
                raise ImportError(
                    "Tesseract 未安装, 请运行: pip install pytesseract pillow "
                    "并安装系统 tesseract-ocr 及中文语言包"
                )
        else:
            raise ValueError(f"不支持的 OCR 引擎: {self.engine}")

    def recognize(self, image_path: str | Path) -> List[Tuple[str, float]]:
        """识别图片文字, 返回 [(文本, 置信度), ...]"""
        self._init_ocr()
        image_path = str(image_path)

        if self.engine == "paddle":
            result = self._ocr.ocr(image_path, cls=True)
            texts = []
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]
                    conf = line[1][1]
                    texts.append((text, conf))
            return texts
        elif self.engine == "tesseract":
            img = self._Image.open(image_path)
            text = self._ocr.image_to_string(img, lang="chi_sim+eng")
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            return [(l, 0.8) for l in lines]
        return []

    def extract_info(self, image_path: str | Path,
                     doc_type: str = "auto") -> Dict[str, Optional[str]]:
        """从图片中提取身份证/户口本信息

        Args:
            image_path: 图片路径
            doc_type: 文档类型 - id_card(身份证) / household(户口本) / auto(自动判断)

        Returns:
            包含 name, id_number, gender, village_group 的字典
        """
        texts = self.recognize(image_path)
        full_text = "\n".join([t[0] for t in texts])

        if doc_type == "auto":
            doc_type = self._detect_doc_type(full_text)

        info = {
            "name": None,
            "id_number": None,
            "gender": None,
            "village_group": None,
            "doc_type": doc_type,
            "raw_text": full_text,
        }

        if doc_type == "id_card":
            info.update(self._extract_id_card(texts, full_text))
        elif doc_type == "household":
            info.update(self._extract_household(texts, full_text))
        else:
            info.update(self._extract_id_card(texts, full_text))
            if not info.get("name") or not info.get("id_number"):
                info.update(self._extract_household(texts, full_text))

        return info

    @staticmethod
    def _detect_doc_type(text: str) -> str:
        id_card_keywords = ["公民身份号码", "身份证", "签发机关", "有效期限"]
        household_keywords = ["户号", "户主姓名", "住址", "常住人口登记卡", "户别"]

        id_score = sum(1 for kw in id_card_keywords if kw in text)
        hh_score = sum(1 for kw in household_keywords if kw in text)

        if id_score >= hh_score and id_score > 0:
            return "id_card"
        elif hh_score > 0:
            return "household"
        return "id_card"

    @staticmethod
    def _extract_id_card(texts: List[Tuple[str, float]],
                         full_text: str) -> Dict[str, Optional[str]]:
        result = {}

        id_match = re.search(
            r'\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b',
            full_text
        )
        if id_match:
            result["id_number"] = id_match.group(0).upper()

        name_patterns = [
            r'姓\s*名\s*[:：]?\s*([\u4e00-\u9fa5]{2,4})',
            r'Name\s*[:：]?\s*([\u4e00-\u9fa5]{2,4})',
        ]
        for pat in name_patterns:
            m = re.search(pat, full_text)
            if m:
                result["name"] = m.group(1)
                break

        if "name" not in result:
            for text, conf in texts:
                text_clean = text.strip()
                if re.match(r'^[\u4e00-\u9fa5]{2,4}$', text_clean):
                    if not any(kw in text_clean for kw in
                               ["性别", "民族", "出生", "住址", "公民", "身份", "签发", "有效"]):
                        result["name"] = text_clean
                        break

        gender_match = re.search(r'性\s*别\s*[:：]?\s*([男女])', full_text)
        if gender_match:
            result["gender"] = gender_match.group(1)

        return result

    @staticmethod
    def _extract_household(texts: List[Tuple[str, float]],
                           full_text: str) -> Dict[str, Optional[str]]:
        result = {}

        id_match = re.search(
            r'\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b',
            full_text
        )
        if id_match:
            result["id_number"] = id_match.group(0).upper()

        name_patterns = [
            r'姓\s*名\s*[:：]?\s*([\u4e00-\u9fa5]{2,4})',
            r'户主姓名\s*[:：]?\s*([\u4e00-\u9fa5]{2,4})',
        ]
        for pat in name_patterns:
            m = re.search(pat, full_text)
            if m:
                result["name"] = m.group(1)
                break

        gender_match = re.search(r'性\s*别\s*[:：]?\s*([男女])', full_text)
        if gender_match:
            result["gender"] = gender_match.group(1)

        village_patterns = [
            r'([\u4e00-\u9fa5]+村[\u4e00-\u9fa5]*组)',
            r'([\u4e00-\u9fa5]+村民小组)',
            r'([\u4e00-\u9fa5]+村委会[\u4e00-\u9fa5]*)',
            r'住址\s*[:：]?\s*([\u4e00-\u9fa5\d]+村[\u4e00-\u9fa5\d]*组)',
            r'本市(?:其他)住址\s*[:：]?\s*([\u4e00-\u9fa5\d]+村[\u4e00-\u9fa5\d]*组)',
        ]
        for pat in village_patterns:
            m = re.search(pat, full_text)
            if m:
                result["village_group"] = m.group(1)
                break

        if "village_group" not in result:
            for text, conf in texts:
                if ("村" in text and "组" in text) or "村民小组" in text:
                    clean = re.sub(r'^.*?(?=[\u4e00-\u9fa5])', '', text).strip()
                    if clean:
                        result["village_group"] = clean
                        break

        return result


def extract_id_info(image_path: str | Path,
                    doc_type: str = "auto",
                    engine: str = "auto") -> Dict[str, Optional[str]]:
    """便捷函数: 从图片提取身份证/户口本信息"""
    ocr = IDCardOCR(engine=engine)
    return ocr.extract_info(image_path, doc_type=doc_type)


def save_result(info: Dict, output_path: str | Path) -> Path:
    """将提取结果保存为 JSON 文件"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python id_card_ocr.py <图片路径> [文档类型] [引擎]")
        print("  文档类型: auto / id_card / household")
        print("  引擎: paddle / tesseract")
        sys.exit(1)

    img = sys.argv[1]
    dtype = sys.argv[2] if len(sys.argv) > 2 else "auto"
    eng = sys.argv[3] if len(sys.argv) > 3 else "paddle"

    info = extract_id_info(img, dtype, eng)
    print(json.dumps(info, ensure_ascii=False, indent=2))
