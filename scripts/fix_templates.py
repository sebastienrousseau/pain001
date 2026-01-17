import glob
import re


def fix_templates():
    template_files = glob.glob("pain001/templates/pain.001.001.*/template.xml")

    # Tags to wrap in if blocks
    # Added AdrLine, and others just in case.
    tags_to_fix = [
        "StrtNm",
        "BldgNb",
        "PstCd",
        "TwnNm",
        "Ctry",
        "AdrLine",
        "CtrySubDvsn",
        "Dept",
        "SubDept",
        "Nm",
        "Id",
        "BICFI",
        "IBAN",  # Maybe irrelevant for address but good for safety?
        # Actually Nm is mandatory usually. Leaving it alone unless it breaks.
    ]

    # Narrowing back to likely optional text fields that cause empty tag errors
    tags_to_fix = [
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

    tags_pattern = "|".join(tags_to_fix)
    # UPDATED REGEX: Added \. to the character class for variable name
    pattern_str = r"(<(" + tags_pattern + r")>\{\{([a-zA-Z0-9_\.]+)\}\}</\2>)"
    pattern = re.compile(pattern_str)

    for file_path in template_files:
        print(f"Processing {file_path}...")
        with open(file_path) as f:
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
                any(f"<{t}>" in line for t in tags_to_fix)
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
            with open(file_path, "w") as f:
                f.write("\n".join(new_lines) + "\n")
        else:
            print("  No changes needed.")


if __name__ == "__main__":
    fix_templates()
