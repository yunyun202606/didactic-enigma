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

        ocr_name_keywords = ['姓名', '姓 名', '姓 名:', '姓名:', '姓 名：', '姓名：',
                              '名', 'name', 'Name', 'NAME']
        name_value = None

        for i, (text, conf) in enumerate(texts):
            text_clean = text.strip()
            matched_kw = None
            for kw in ocr_name_keywords:
                if kw in text_clean:
                    matched_kw = kw
                    break
            if matched_kw:
                after = text_clean.split(matched_kw, 1)[1].strip()
                after = re.sub(r'^[:：\s]+', '', after)
                after = re.sub(r'[\s　]+', '', after)
                name_m = re.match(r'([\u4e00-\u9fa5]{2,6})', after)
                if name_m:
                    candidate = name_m.group(1)
                    if not any(kw in candidate for kw in
                               ['性别', '民族', '出生', '住址', '公民', '身份', '签发', '有效']):
                        name_value = candidate
                        break
                elif i + 1 < len(texts):
                    next_text = texts[i + 1][0].strip()
                    next_text = re.sub(r'[\s　]+', '', next_text)
                    name_m = re.match(r'([\u4e00-\u9fa5]{2,6})', next_text)
                    if name_m:
                        candidate = name_m.group(1)
                        if not any(kw in candidate for kw in
                                   ['性别', '民族', '出生', '住址', '公民', '身份', '签发', '有效']):
                            name_value = candidate
                            break

        if not name_value:
            for pat in [
                r'姓\s*名\s*[:：]?\s*([\u4e00-\u9fa5]{2,6})',
                r'姓\s*名\s+([\u4e00-\u9fa5]{2,6})',
                r'Name\s*[:：]?\s*([\u4e00-\u9fa5]{2,6})',
            ]:
                m = re.search(pat, full_text)
                if m:
                    candidate = m.group(1).strip()
                    if not any(kw in candidate for kw in
                               ['性别', '民族', '出生', '住址', '公民', '身份', '签发', '有效']):
                        name_value = candidate
                        break

        if not name_value:
            id_idx = full_text.find(result.get("id_number", ""))
            if id_idx > 0:
                above_text = full_text[:id_idx]
                name_candidates = re.findall(r'\n([\u4e00-\u9fa5]{2,6})\n', above_text)
                valid = [c for c in name_candidates
                         if not any(kw in c for kw in
                                    ['性别', '民族', '出生', '住址', '公民', '身份', '签发',
                                     '有效', '年月', '期限', '机关'])
                         and 2 <= len(c) <= 6]
                if valid:
                    name_value = valid[-1]

        if not name_value:
            candidates = []
            for text, conf in texts:
                t = text.strip()
                t = re.sub(r'[\s　]+', '', t)
                if re.match(r'^[\u4e00-\u9fa5]{2,6}$', t):
                    if not any(kw in t for kw in
                               ['性别', '民族', '出生', '住址', '公民', '身份', '签发',
                                '有效', '年月', '期限', '机关']):
                        candidates.append((t, conf))
            if candidates:
                candidates.sort(key=lambda x: -x[1])
                name_value = candidates[0][0]

        if name_value:
            result["name"] = name_value

        gender_match = re.search(r'性\s*别\s*[:：]?\s*([男女])', full_text)
        if gender_match:
            result["gender"] = gender_match.group(1)
        else:
            for text, _ in texts:
                m = re.search(r'([男女])\s*性', text)
                if m:
                    result["gender"] = m.group(1)
                    break

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

        name_value = None
        head_name = None
        personal_name = None

        for i, (text, conf) in enumerate(texts):
            text_clean = text.strip()
            text_one_line = re.sub(r'[\s　]+', '', text_clean)

            if '户主姓名' in text_clean or '户主 姓名' in text_clean:
                after = re.split(r'户主\s*姓名', text_clean, 1)[1].strip()
                after = re.sub(r'^[:：\s]+', '', after)
                after = re.sub(r'[\s　]+', '', after)
                m = re.match(r'([\u4e00-\u9fa5]{2,6})', after)
                if m:
                    head_name = m.group(1)
                elif i + 1 < len(texts):
                    next_t = re.sub(r'[\s　]+', '', texts[i + 1][0].strip())
                    m = re.match(r'([\u4e00-\u9fa5]{2,6})', next_t)
                    if m:
                        head_name = m.group(1)
                continue

            if '姓名' in text_clean and '户主' not in text_clean:
                after = text_clean.split('姓名', 1)[1].strip()
                after = re.sub(r'^[:：\s]+', '', after)
                after = re.sub(r'[\s　]+', '', after)
                m = re.match(r'([\u4e00-\u9fa5]{2,6})', after)
                if m:
                    candidate = m.group(1)
                    if not any(kw in candidate for kw in
                               ['性别', '民族', '出生', '住址', '公民', '身份', '签发', '有效', '户主']):
                        personal_name = candidate
                        break
                elif i + 1 < len(texts):
                    next_t = re.sub(r'[\s　]+', '', texts[i + 1][0].strip())
                    m = re.match(r'([\u4e00-\u9fa5]{2,6})', next_t)
                    if m:
                        candidate = m.group(1)
                        if not any(kw in candidate for kw in
                                   ['性别', '民族', '出生', '住址', '公民', '身份', '签发', '有效', '户主']):
                            personal_name = candidate
                            break

        if personal_name:
            name_value = personal_name
        elif head_name:
            name_value = head_name

        if not name_value:
            for pat in [
                r'(?<!户主)姓\s*名\s*[:：]?\s*([\u4e00-\u9fa5]{2,6})',
                r'姓\s*名\s+([\u4e00-\u9fa5]{2,6})',
            ]:
                m = re.search(pat, full_text)
                if m:
                    candidate = m.group(1).strip()
                    if not any(kw in candidate for kw in
                               ['性别', '民族', '出生', '住址', '公民', '身份', '签发',
                                '有效', '年月', '期限', '机关', '户主', '与户主']):
                        if 2 <= len(candidate) <= 6:
                            name_value = candidate
                            break

        if not name_value:
            id_idx = full_text.find(result.get("id_number", ""))
            if id_idx > 0:
                above_text = full_text[:id_idx]
                found_names = re.findall(r'\n([\u4e00-\u9fa5]{2,6})\n', above_text)
                valid = [c for c in found_names
                         if not any(kw in c for kw in
                                    ['性别', '民族', '出生', '住址', '公民', '身份', '签发',
                                     '有效', '年月', '期限', '机关', '户主', '与户主',
                                     '户别', '户号', '登记', '日期', '文化', '职业'])
                         and 2 <= len(c) <= 6]
                if valid:
                    name_value = valid[-1]

        if not name_value:
            candidates = []
            for text, conf in texts:
                t = re.sub(r'[\s　]+', '', text.strip())
                if re.match(r'^[\u4e00-\u9fa5]{2,6}$', t):
                    if not any(kw in t for kw in
                               ['性别', '民族', '出生', '住址', '公民', '身份', '签发',
                                '有效', '年月', '期限', '机关', '户主', '与户主',
                                '户别', '户号', '登记', '日期', '文化', '职业', '婚姻',
                                '兵役', '身高', '血型', '住址']):
                        candidates.append((t, conf))
            if candidates:
                candidates.sort(key=lambda x: -x[1])
                name_value = candidates[0][0]

        if name_value:
            result["name"] = name_value

        gender_match = re.search(r'性\s*别\s*[:：]?\s*([男女])', full_text)
        if gender_match:
            result["gender"] = gender_match.group(1)
        else:
            for text, _ in texts:
                m = re.search(r'([男女])\s*性', text)
                if m:
                    result["gender"] = m.group(1)
                    break

        def _extract_village(text: str) -> Optional[str]:
            clean_text = re.sub(r'[\d]+[号弄栋单元室]?[\s\d]*$', '', text)
            clean_text = re.sub(r'\s+', '', clean_text)

            boundary_chars = set('省市区县镇乡街道路号楼村组')

            suffix_patterns = [
                (r'村[\u4e00-\u9fa5\d]{1,4}组', 8),
                (r'村民小组', 8),
                (r'村村民小组', 8),
                (r'社区居民小组', 8),
                (r'社区[\u4e00-\u9fa5\d]{1,4}组', 8),
                (r'居委会[\u4e00-\u9fa5\d]{1,4}组', 8),
                (r'居民小组', 8),
                (r'村(?:居)?委会', 8),
                (r'社区居委会', 8),
                (r'村生产队', 8),
                (r'生产队', 6),
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
                        res = village_name + suffix
                        if len(res) >= 3:
                            return res
            return None

        vg = None

        for i, (text, conf) in enumerate(texts):
            if any(kw in text for kw in ['住址', '本市住址', '本市其他住址', '籍贯']):
                after = text
                for kw in ['住址', '本市住址', '本市其他住址', '籍贯']:
                    if kw in after:
                        after = after.split(kw, 1)[1]
                        break
                after = re.sub(r'^[:：\s]+', '', after)
                if after:
                    v = _extract_village(after)
                    if v:
                        vg = v
                        break
                elif i + 1 < len(texts):
                    v = _extract_village(texts[i + 1][0])
                    if v:
                        vg = v
                        break

        if not vg:
            vg = _extract_village(full_text)

        if not vg:
            village_keywords = ["村", "组", "社区", "居委会", "村民小组", "居民小组",
                                 "村委会", "生产队"]
            candidates = []
            for text, conf in texts:
                text_clean = text.strip()
                score = sum(1 for kw in village_keywords if kw in text_clean)
                if score >= 2:
                    v = _extract_village(text_clean)
                    if v and len(v) >= 3:
                        candidates.append((v, conf, score))
            if candidates:
                candidates.sort(key=lambda x: (-x[2], -x[1]))
                vg = candidates[0][0]

        if vg:
            result["village_group"] = vg

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
