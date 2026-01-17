import glob
import re

# Narrowing back to likely optional text fields that cause empty tag errors
TAGS_TO_FIX = [
    "StrtNm",
    "BldgNb",
    "PstCd",
    "TwnNm",
    "Ctry",
    "AdrLine",
    "CtrySubDvsn",
    "Dept",
    "SubDept",
]


def fix_templates():
    template_files = glob.glob("pain001/templates/pain.001.001.*/template.xml")

    tags_pattern = "|".join(TAGS_TO_FIX)
    # UPDATED REGEX: Added \. to the character class for variable name
    pattern_str = r"(<(" + tags_pattern + r")>\{\{([a-zA-Z0-9_\.]+)\}\}</\2>)"
    pattern = re.compile(pattern_str)

    for file_path in template_files:
        print(f"Processing {file_path}...")
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # No need to read line by line if we trust the regex and replacement
        # But per-line allows us to count changes and avoid multi-line regex complexity

        def replacement(match):
            full_tag = match.group(1)
            # tag_name = match.group(2)
            var_name = match.group(3)
            return f"{{% if {var_name} %}}{full_tag}{{% endif %}}"

        new_lines = []
        lines = content.splitlines()
        changes_count = 0

        for line in lines:
            # Check if line contains one of the targets AND is not already wrapped in jinja if
            # Using loop to check tag presence to speed up
            if (
                any(f"<{t}>" in line for t in TAGS_TO_FIX)
                and "{% if" not in line
            ):
                new_line = pattern.sub(replacement, line)
                if new_line != line:
                    changes_count += 1
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        if changes_count > 0:
            print(f"  Fixed {changes_count} occurrences.")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
        else:
            print("  No changes needed.")


if __name__ == "__main__":
    fix_templates()
