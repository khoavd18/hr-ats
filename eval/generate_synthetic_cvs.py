"""Offline synthetic CVs. Run from backend: uv run python ../eval/generate_synthetic_cvs.py.

All identities, contacts, employers and employment histories are fabricated.
No provider calls, system fonts, current dates or unseeded random generators are used.
"""

import argparse
import json
import random
from datetime import UTC, datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pymupdf
from docx import Document
from docx.shared import Inches, Pt
from PIL import Image
from pydantic import ValidationError

if __package__:
    from .schemas import CVLabel, Education, Experience, Job, JobDataset
else:
    from schemas import CVLabel, Education, Experience, Job, JobDataset

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = 20261108
LAYOUTS = ("one_column", "two_column", "table", "avatar", "english", "scan")
REGIONS = ("north", "central", "south")
# The regional buckets ensure fixture coverage; they do not classify real people's names.
NAMES = {
    "north": {
        "Nam": ("Nguyễn Minh Khôi", "Trần Đức Lâm", "Phạm Quang Tùng"),
        "Nữ": ("Nguyễn Thu Hà", "Trần Ngọc Mai", "Phạm Bảo Anh"),
    },
    "central": {
        "Nam": ("Hoàng Đình Phúc", "Võ Nhật Huy", "Đặng Hữu An"),
        "Nữ": ("Hoàng Thị Huế", "Võ Thanh Thảo", "Đặng Ngọc Trâm"),
    },
    "south": {
        "Nam": ("Huỳnh Quốc Bảo", "Lê Thành Đạt", "Trương Minh Khang"),
        "Nữ": ("Huỳnh Ngọc Hân", "Lê Mỹ Duyên", "Trương Kim Ngân"),
    },
}
SCHOOLS = {
    "north": "Đại học Mô phỏng Miền Bắc",
    "central": "Đại học Mô phỏng Miền Trung",
    "south": "Đại học Mô phỏng Miền Nam",
}
COMPANIES = (
    "Công ty Giả lập Mây Tím",
    "Công ty Giả lập Sao Giấy",
    "Công ty Giả lập Lá Vuông",
    "Công ty Giả lập Sóng Cam",
    "Công ty Giả lập Mầm Bạc",
    "Công ty Giả lập Đồi Lam",
)
PROFILES = {
    "backend": {
        "title": ("Lập trình viên backend", "Backend developer"),
        "major": ("Công nghệ thông tin", "Information technology"),
        "skills": ("python", "sql", "fastapi", "docker", "redis"),
        "work": (
            "Xây dựng API quản lý đơn hàng; viết kiểm thử và tối ưu truy vấn dữ liệu.",
            "Built order management APIs, wrote tests and improved database queries.",
        ),
    },
    "frontend": {
        "title": ("Lập trình viên frontend", "Frontend developer"),
        "major": ("Kỹ thuật phần mềm", "Software engineering"),
        "skills": ("javascript", "react", "typescript", "css", "accessibility"),
        "work": (
            "Phát triển giao diện quản lý kho; kiểm tra biểu mẫu và hiển thị trên điện thoại.",
            "Developed inventory interfaces, validated forms and supported mobile screens.",
        ),
    },
    "accounting": {
        "title": ("Nhân viên kế toán", "Accountant"),
        "major": ("Kế toán", "Accounting"),
        "skills": ("bookkeeping", "excel", "tax reporting", "reconciliation", "budgeting"),
        "work": (
            "Đối chiếu công nợ, nhập chứng từ và lập báo cáo thu chi hằng tháng.",
            "Reconciled accounts, recorded invoices and prepared monthly financial reports.",
        ),
    },
    "sales": {
        "title": ("Nhân viên kinh doanh", "Sales executive"),
        "major": ("Quản trị kinh doanh", "Business administration"),
        "skills": ("b2b sales", "crm", "negotiation", "forecasting", "account management"),
        "work": (
            "Tư vấn khách hàng doanh nghiệp, cập nhật cơ hội và theo dõi hợp đồng.",
            "Advised business customers, updated sales opportunities and tracked contracts.",
        ),
    },
    "marketing": {
        "title": ("Chuyên viên marketing", "Marketing specialist"),
        "major": ("Truyền thông", "Communications"),
        "skills": ("content marketing", "seo", "analytics", "copywriting", "campaign planning"),
        "work": (
            "Lập lịch nội dung, đo hiệu quả chiến dịch và cải thiện trang giới thiệu sản phẩm.",
            "Planned content, measured campaigns and improved product landing pages.",
        ),
    },
    "hr": {
        "title": ("Chuyên viên nhân sự", "HR specialist"),
        "major": ("Quản trị nhân lực", "Human resource management"),
        "skills": ("recruitment", "onboarding", "payroll", "hr reporting", "training"),
        "work": (
            "Điều phối lịch phỏng vấn, hỗ trợ hội nhập và tổng hợp báo cáo nhân sự.",
            "Coordinated interviews, supported onboarding and prepared HR reports.",
        ),
    },
}


def make_jobs() -> list[Job]:
    """Five explicit fixture jobs; HR CVs provide unrelated-career negative examples."""
    return [
        Job(
            id=f"job_{career}",
            title=profile["title"][0],
            description=f"Vị trí tại đơn vị giả lập. {profile['work'][0]}",
            must_have=[*profile["skills"][:2], "Ít nhất 3 năm kinh nghiệm liên quan"],
            nice_to_have=list(profile["skills"][2:4]),
        )
        for career, profile in PROFILES.items()
        if career != "hr"
    ]


def make_labels(count: int, seed: int) -> list[CVLabel]:
    rng = random.Random(seed)
    labels = []
    for index in range(count):
        cv_id = f"cv_{index + 1:04d}"
        layout = LAYOUTS[index % len(LAYOUTS)]
        career = tuple(PROFILES)[(index // 6 + index % 6) % 6]
        region = REGIONS[(index // 2) % 3]
        gender = ("Nam", "Nữ")[index % 2]
        lang = int(layout == "english")
        profile = PROFILES[career]
        scenario = (index // 6) % 3
        years = (1, 2, 6)[scenario]
        title = profile["title"][lang]
        # All dates are relative to 2026-01-01, never the wall clock.
        start_year = 2026 - years
        companies = rng.sample(COMPANIES, 2 if years == 6 else 1)
        experience = [
            Experience(
                company=company,
                title=title,
                start=f"{start_year + step * 3}-01",
                end=f"{start_year + (step + 1) * 3 if years == 6 else 2026}-01",
                description=profile["work"][lang],
            )
            for step, company in enumerate(companies)
        ]
        expected = {
            job.id: ("low", "medium", "high")[scenario] if job.id == f"job_{career}" else "low"
            for job in make_jobs()
        }
        extension = "pdf" if layout == "scan" or (index // 6) % 2 == 0 else "docx"
        labels.append(
            CVLabel(
                id=cv_id,
                file_name=f"{cv_id}.{extension}",
                layout=layout,
                language="en" if lang else "vi",
                career=career,
                region=region,
                gender=gender,
                full_name=rng.choice(NAMES[region][gender]),
                email=f"{cv_id}@example.com",
                phone=f"09{index // 1000:02d} 000 {index % 1000:03d}",
                date_of_birth=f"{start_year - 23}-06-15",
                location=f"Số {index + 1}, Đường Mô Phỏng, Khu {region}",
                current_title=title,
                years_experience=years,
                skills=list(profile["skills"][: (1, 2, 5)[scenario]]),
                experience=experience,
                education=[
                    Education(
                        school=SCHOOLS[region],
                        degree="Bachelor" if lang else "Cử nhân",
                        major=profile["major"][lang],
                        start=f"{start_year - 4}-09",
                        end=f"{start_year}-06",
                    )
                ],
                expected_level=expected,
            )
        )
    return labels


def sections(label: CVLabel) -> list[tuple[str, str]]:
    en = label.language == "en"
    gender = ("Male" if label.gender == "Nam" else "Female") if en else label.gender
    contact = [
        f"Email: {label.email}",
        f"{'Phone' if en else 'Điện thoại'}: {label.phone}",
        f"{'Address' if en else 'Địa chỉ'}: {label.location}",
        f"{'Date of birth' if en else 'Ngày sinh'}: {label.date_of_birth}",
        f"{'Gender' if en else 'Giới tính'}: {gender}",
    ]
    experience = "\n\n".join(
        f"{item.company}\n{item.title} | {item.start} - {item.end}\n{item.description}"
        for item in label.experience
    )
    education = "\n".join(
        f"{item.school}\n{item.degree} - {item.major}\n{item.start} - {item.end}"
        for item in label.education
    )
    return [
        ("Contact" if en else "Liên hệ", "\n".join(contact)),
        (
            "Profile" if en else "Giới thiệu",
            (
                f"{label.years_experience} years of experience. Seeking a role in a collaborative "
                "team with clear goals and opportunities to develop professional skills."
                if en
                else f"{label.years_experience} năm kinh nghiệm. Mong muốn làm việc trong đội ngũ "
                "có mục tiêu rõ ràng, cùng đồng nghiệp nâng cao chuyên môn và cải tiến quy trình."
            ),
        ),
        ("Skills" if en else "Kỹ năng", ", ".join(label.skills)),
        ("Experience" if en else "Kinh nghiệm", experience),
        ("Education" if en else "Học vấn", education),
    ]


@lru_cache(maxsize=1)
def font_bytes() -> bytes:
    # Bundle one OFL font: CJK fallback fonts can silently lack Vietnamese glyphs.
    return (Path(__file__).parent / "assets/NotoSans-Regular.ttf").read_bytes()


def pdf_bytes(label: CVLabel) -> bytes:
    with pymupdf.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_font(fontname="Synthetic", fontbuffer=font_bytes())

        def text(rect, content, size=10):
            remaining = page.insert_textbox(
                rect, content, fontname="Synthetic", fontsize=size, lineheight=1.4
            )
            if remaining < 0:
                raise ValueError("Synthetic PDF text overflow")

        text((32, 24, 475, 65), label.full_name, 20)
        text((32, 70, 475, 100), label.current_title, 12)
        blocks = sections(label)
        if label.layout == "avatar":
            page.draw_rect((490, 24, 560, 94), color=None, fill=(0.2, 0.5, 0.6))
        if label.layout == "two_column":
            text((32, 115, 210, 430), f"{blocks[0][0]}\n{blocks[0][1]}")
            text((32, 455, 210, 730), f"{blocks[2][0]}\n{blocks[2][1]}")
            text(
                (238, 115, 560, 760),
                "\n\n".join(f"{blocks[i][0]}\n{blocks[i][1]}" for i in (1, 3, 4)),
            )
        elif label.layout == "table":
            y = 110
            for (heading, body), height in zip(blocks, (125, 85, 65, 220, 110), strict=True):
                page.draw_rect((32, y, 170, y + height), color=(0.6, 0.6, 0.6))
                page.draw_rect((170, y, 560, y + height), color=(0.6, 0.6, 0.6))
                text((40, y + 8, 160, y + height - 4), heading)
                text((180, y + 8, 550, y + height - 4), body)
                y += height
        else:
            text((32, 115, 560, 770), "\n\n".join(f"{h}\n{b}" for h, b in blocks))
        text(
            (32, 800, 560, 830),
            "SYNTHETIC DATA - NOT A REAL PERSON"
            if label.language == "en"
            else "DỮ LIỆU GIẢ LẬP - KHÔNG PHẢI HỒ SƠ NGƯỜI THẬT",
            8,
        )
        doc.set_metadata(
            {
                "title": label.id,
                "author": "hr-ats synthetic generator",
                "creationDate": "D:20000101000000Z",
                "modDate": "D:20000101000000Z",
            }
        )
        # MuPDF's subset font tags vary across OS builds. The complete OFL font
        # compresses well and keeps the whole sample corpus under 30 MB.
        return doc.tobytes(garbage=4, deflate=True, no_new_id=True)


def scanned_pdf_bytes(source: bytes, rng: random.Random) -> bytes:
    with pymupdf.open(stream=source, filetype="pdf") as doc:
        pix = doc[0].get_pixmap(dpi=120, colorspace=pymupdf.csGRAY)
    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    image = image.rotate(rng.choice((-0.8, -0.5, 0.5, 0.8)), fillcolor=245)
    # Sparse seeded scanner noise keeps the image legible and fixture size small.
    for _ in range(2500):
        image.putpixel(
            (rng.randrange(image.width), rng.randrange(image.height)), rng.randrange(256)
        )
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=78, optimize=False)
    with pymupdf.open() as scan:
        page = scan.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=buffer.getvalue())
        scan.set_metadata({"title": "Synthetic scan", "creationDate": "D:20000101000000Z"})
        return scan.tobytes(garbage=4, deflate=True, no_new_id=True)


def docx_bytes(label: CVLabel) -> bytes:
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.27), Inches(11.69)
    section.top_margin = section.bottom_margin = Inches(0.45)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Arial", Pt(10)
    normal.paragraph_format.space_after = Pt(4)
    doc.add_heading(label.full_name, 0)
    doc.add_paragraph(label.current_title)
    if label.layout == "avatar":
        buffer = BytesIO()
        # BMP pixels avoid platform-specific PNG compression in Pillow wheels.
        Image.new("RGB", (100, 100), (51, 128, 153)).save(buffer, format="BMP")
        doc.add_picture(BytesIO(buffer.getvalue()), width=Inches(0.7))
    blocks = sections(label)
    if label.layout == "two_column":
        table = doc.add_table(rows=1, cols=2)
        for column, indices in enumerate(((0, 2), (1, 3, 4))):
            cell = table.cell(0, column)
            for index in indices:
                cell.add_paragraph(blocks[index][0], style="Heading 2")
                cell.add_paragraph(blocks[index][1])
    elif label.layout == "table":
        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        for heading, body in blocks:
            cells = table.add_row().cells
            cells[0].text, cells[1].text = heading, body
    else:
        for heading, body in blocks:
            doc.add_heading(heading, 2)
            doc.add_paragraph(body)
    section.footer.paragraphs[0].text = (
        "SYNTHETIC DATA - NOT A REAL PERSON"
        if label.language == "en"
        else "DỮ LIỆU GIẢ LẬP - KHÔNG PHẢI HỒ SƠ NGƯỜI THẬT"
    )
    props = doc.core_properties
    props.author = props.last_modified_by = "hr-ats synthetic generator"
    props.created = props.modified = datetime(2000, 1, 1, tzinfo=UTC)
    props.title, props.revision = label.id, 1
    buffer = BytesIO()
    doc.save(buffer)
    # DOCX is a ZIP: normalize entry order and timestamps, including image entries.
    output = BytesIO()
    with ZipFile(buffer) as source, ZipFile(output, "w", compression=ZIP_DEFLATED) as target:
        for name in sorted(source.namelist()):
            entry = ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            entry.create_system = 0
            entry.compress_type = ZIP_DEFLATED
            target.writestr(entry, source.read(name), compresslevel=9)
    return output.getvalue()


def write_json(path: Path, model: CVLabel | JobDataset) -> None:
    path.write_bytes(
        (json.dumps(model.model_dump(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def generate_dataset(*, count: int, seed: int, out: Path) -> None:
    if not 1 <= count <= 10000:
        raise ValueError("count must be between 1 and 10000")
    labels = make_labels(count, seed)
    expected_names = {"jobs.json"} | {
        name for label in labels for name in (label.file_name, f"{label.id}.json")
    }
    existing = {path.name for path in out.iterdir()} - {".gitkeep"} if out.exists() else set()
    # Do not delete stale files or overwrite arbitrary user documents. A rerun may
    # replace a complete synthetic set of the same shape, never another dataset.
    if existing:
        if existing != expected_names or any((out / name).is_symlink() for name in existing):
            raise ValueError("Use an empty output directory or a complete matching synthetic set")
        JobDataset.model_validate_json((out / "jobs.json").read_bytes())
        for label in labels:
            old = CVLabel.model_validate_json((out / f"{label.id}.json").read_bytes())
            if old.id != label.id or old.file_name != label.file_name:
                raise ValueError("Existing labels do not match the generated file set")
    out.mkdir(parents=True, exist_ok=True)
    for index, label in enumerate(labels):
        if label.file_name.endswith(".docx"):
            payload = docx_bytes(label)
        else:
            payload = pdf_bytes(label)
            if label.layout == "scan":
                payload = scanned_pdf_bytes(payload, random.Random(f"{seed}:scan:{index}"))
        (out / label.file_name).write_bytes(payload)
        write_json(out / f"{label.id}.json", label)
    write_json(
        out / "jobs.json",
        JobDataset(
            seed=seed,
            jobs=make_jobs(),
            expected_level={label.id: label.expected_level for label in labels},
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data/sample_cvs")
    args = parser.parse_args()
    try:
        generate_dataset(count=args.count, seed=args.seed, out=args.out)
    except ValidationError:
        # ValidationError includes raw field values by default. Keep contact
        # fields out of terminal/CI logs when an existing label is corrupted.
        parser.error("Fixture data failed schema validation")
    except ValueError as error:
        parser.error(str(error))
    # Aggregate metadata only; never log CV fields or generated contact details.
    print(f"Generated {args.count} synthetic CVs and labels (seed={args.seed}).")


if __name__ == "__main__":
    main()
