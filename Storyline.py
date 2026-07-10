import os
import zipfile
import tempfile
import xml.etree.ElementTree as etree

story_path = input("Please enter .story path: ")
xliff_path = input("Please enter .xlf path: ")

def export_story_to_xliff(story_path, xliff_path,
                         source_lang="en-US", target_lang=""):
    # unzip …
    tempdir = tempfile.mkdtemp()
    with zipfile.ZipFile(story_path, 'r') as zipf:
        zipf.extractall(tempdir)

    # build XLIFF root
    xliff = etree.Element("xliff", {
        "version": "1.2",
        "xmlns": "urn:oasis:names:tc:xliff:document:1.2"
    })
    file_el = etree.SubElement(xliff, "file", {
        "source-language": source_lang,
        "target-language": target_lang,
        "datatype": "plaintext",
        "original": os.path.basename(story_path),
    })
    body = etree.SubElement(file_el, "body")

    unit_id = 1
    # Walk through all XML files and all elements
    for root_dir, _, files in os.walk(tempdir):
        for fn in files:
            if fn.lower().endswith('.xml'):
                xml_path = os.path.join(root_dir, fn)
                tree = etree.parse(xml_path)
                
                # Instead of xpath, use .iter() to visit every element
                for elem in tree.iter():
                    text = (elem.text or "").strip()
                    if not text:
                        continue

                    tu = etree.SubElement(body, "trans-unit", id=str(unit_id))
                    note = etree.SubElement(tu, "note")
                    note.text = f"{os.path.relpath(xml_path, tempdir)}::{elem.tag}"
                    src = etree.SubElement(tu, "source")
                    src.text = text
                    etree.SubElement(tu, "target")
                    unit_id += 1

    # Write out the XLIFF
    out_tree = etree.ElementTree(xliff)
    out_tree.write(
        xliff_path,
        encoding="utf-8",
        xml_declaration=True
    )
    print(f"✔️ Exported {unit_id-1} text units to {xliff_path}")
