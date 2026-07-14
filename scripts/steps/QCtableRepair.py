import os
import shutil
import zipfile
import tempfile
import xml.etree.ElementTree as ET

file_path = r"D:\University\master\QC2026\2026\0422_CBCP\CBCP_QC.xlsx"
backup_path = file_path + ".bak"

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)

def repair_xlsx_styles_inplace(xlsx_path):
    if not os.path.exists(backup_path):
        shutil.copy2(xlsx_path, backup_path)
        print(f"已备份原文件 -> {backup_path}")

    tmp_fd, tmp_zip_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(tmp_fd)

    repaired = False

    with zipfile.ZipFile(xlsx_path, "r") as zin, zipfile.ZipFile(tmp_zip_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)

            if item.filename == "xl/styles.xml":
                root = ET.fromstring(data)
                fills = root.find(f".//{{{NS}}}fills")

                if fills is not None:
                    for fill in list(fills):
                        # 只接受 patternFill / gradientFill
                        valid_children = {
                            f"{{{NS}}}patternFill",
                            f"{{{NS}}}gradientFill",
                        }
                        children = list(fill)

                        if len(children) == 0 or any(child.tag not in valid_children for child in children):
                            # 清空非法 fill，替换成安全默认 patternFill
                            for child in list(fill):
                                fill.remove(child)
                            ET.SubElement(fill, f"{{{NS}}}patternFill")
                            repaired = True

                    # 顺手校正 count
                    fills.set("count", str(len(list(fills))))

                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)

            zout.writestr(item, data)

    shutil.move(tmp_zip_path, xlsx_path)

    if repaired:
        print("styles.xml 已修复并覆盖原文件。")
    else:
        print("未发现明显异常 fill，但文件已重新写回。")

repair_xlsx_styles_inplace(file_path)
print("修复完成。你现在可以重新运行 openpyxl 脚本。")