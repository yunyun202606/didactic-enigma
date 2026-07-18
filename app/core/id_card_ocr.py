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
            r'姓\s*名\s*[:：]?\s*([\u4e00-\u9fa5]{2,6})',
            r'姓\s*名\s+([\u4e00-\u9fa5]{2,6})',
            r'^\s*([\u4e00-\u9fa5]{2,6})\s*$',
            r'Name\s*[:：]?\s*([\u4e00-\u9fa5]{2,6})',
            r'姓名\s*([\u4e00-\u9fa5]{2,6})',
        ]

        name_found = False
        for pat in name_patterns:
            m = re.search(pat, full_text)
            if m:
                name_candidate = m.group(1).strip()
                if not any(kw in name_candidate for kw in
                           ["性别", "民族", "出生", "住址", "公民", "身份", "签发", "有效", "年月", "期限", "机关"]):
                    if len(name_candidate) >= 2 and len(name_candidate) <= 6:
                        result["name"] = name_candidate
                        name_found = True
                        break

        if not name_found:
            gender_idx = len(full_text)
            gender_match = re.search(r'性\s*别', full_text)
            if gender_match:
                gender_idx = gender_match.start()

            name_candidates = []
            for text, conf in texts:
                text_clean = text.strip()
                if re.match(r'^[\u4e00-\u9fa5]{2,6}$', text_clean):
                    if not any(kw in text_clean for kw in
                               ["性别", "民族", "出生", "住址", "公民", "身份", "签发", "有效", "年月", "期限", "机关"]):
                        name_candidates.append((text_clean, conf))

            if name_candidates:
                name_candidates.sort(key=lambda x: -x[1])
                result["name"] = name_candidates[0][0]

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
            r'(?<!户主)姓\s*名\s*[:：]?\s*([\u4e00-\u9fa5]{2,6})',
            r'(?<!户主)姓\s*名\s+([\u4e00-\u9fa5]{2,6})',
            r'^姓名\s*([\u4e00-\u9fa5]{2,6})',
            r'户主姓名\s*[:：]?\s*([\u4e00-\u9fa5]{2,6})',
            r'户主姓名\s+([\u4e00-\u9fa5]{2,6})',
        ]
        name_found = False
        for pat in name_patterns:
            m = re.search(pat, full_text)
            if m:
                name_candidate = m.group(1).strip()
                if not any(kw in name_candidate for kw in
                           ["性别", "民族", "出生", "住址", "公民", "身份", "签发", "有效", "年月", "期限", "机关", "户主", "与户主"]):
                    if len(name_candidate) >= 2 and len(name_candidate) <= 6:
                        result["name"] = name_candidate
                        name_found = True
                        break

        if not name_found:
            name_candidates = []
            for text, conf in texts:
                text_clean = text.strip()
                if re.match(r'^[\u4e00-\u9fa5]{2,6}$', text_clean):
                    if not any(kw in text_clean for kw in
                               ["性别", "民族", "出生", "住址", "公民", "身份", "签发", "有效",
                                "年月", "期限", "机关", "户主", "与户主", "户别", "户号", "住址",
                                "登记", "日期", "文化", "职业", "婚姻", "兵役", "身高", "血型"]):
                        name_candidates.append((text_clean, conf))
            if name_candidates:
                name_candidates.sort(key=lambda x: -x[1])
                result["name"] = name_candidates[0][0]

        gender_match = re.search(r'性\s*别\s*[:：]?\s*([男女])', full_text)
        if gender_match:
            result["gender"] = gender_match.group(1)

        def _extract_village(text: str) -> Optional[str]:
            clean_text = re.sub(r'[\d]+[号弄栋单元室]?[\s\d]*$', '', text)
            clean_text = re.sub(r'\s+', '', clean_text)

            boundary_chars = set('省市区县镇乡街道路号楼')

            suffix_patterns = [
                (r'村[\u4e00-\u9fa5\d]{1,4}组', 8),
                (r'村民小组', 8),
                (r'社区居民小组', 8),
                (r'社区[\u4e00-\u9fa5\d]{1,4}组', 8),
                (r'居委会[\u4e00-\u9fa5\d]{1,4}组', 8),
                (r'居民小组', 8),
                (r'村(?:居)?委会', 8),
                (r'社区居委会', 8),
            ]

            for suffix_pat, max_prefix in suffix_patterns:
                for m in re.finditer(suffix_pat, clean_text):
                    suffix = m.group(0)
                    start = m.start()

                    prefix_start = max(0, start - max_prefix)
                    prefix = clean_text[prefix_start:start]

                    cut = 0
                    for i in range(len(prefix) - 1, -1, -1):
                        if prefix[i] in boundary_chars:
                            cut = i + 1
                            break

                    village_name = prefix[cut:]
                    if len(village_name) >= 2 and len(village_name) <= max_prefix:
                        result = village_name + suffix
                        if len(result) >= 3:
                            return result
            return None

        vg = _extract_village(full_text)
        if vg:
            result["village_group"] = vg
        else:
            addr_patterns = [
                r'(?:住址|本市住址|本市其他住址)\s*[:：]?\s*(.*)',
            ]
            addr_text = None
            for pat in addr_patterns:
                m = re.search(pat, full_text)
                if m:
                    addr_text = m.group(1).strip()
                    break
            if addr_text:
                vg = _extract_village(addr_text)
                if vg:
                    result["village_group"] = vg

        if "village_group" not in result:
            village_keywords = ["村", "组", "社区", "居委会", "村民小组", "居民小组", "村委会"]
            candidates = []
            for text, conf in texts:
                text_clean = text.strip()
                score = sum(1 for kw in village_keywords if kw in text_clean)
                if score >= 2:
                    vg = _extract_village(text_clean)
                    if vg and len(vg) >= 3:
                        candidates.append((vg, conf, score))
            if candidates:
                candidates.sort(key=lambda x: (-x[2], -x[1]))
                result["village_group"] = candidates[0][0]

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
