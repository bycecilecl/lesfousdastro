def extract_points_forts_from_placements(placements_str: str) -> str:
    """
    Extrait la section Points forts depuis placements_str.
    Compatible avec :
    - ### Points forts
    - ### Points forts du thème
    - ## Points forts
    """

    if not placements_str:
        return ""

    lines = placements_str.splitlines()

    points_forts_lines = []
    in_section = False

    for line in lines:
        raw_line = line.strip()
        line_lower = raw_line.lower()

        if line_lower.startswith("#") and "points forts" in line_lower:
            in_section = True
            continue

        if in_section and raw_line.startswith("#"):
            break

        if in_section and raw_line:
            clean_line = raw_line.lstrip("-• ").strip()

            if clean_line:
                points_forts_lines.append(clean_line)

    return "\n".join(points_forts_lines)