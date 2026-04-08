import re
import json
import pdfplumber

class IssueParser:
    def __init__(self):
        # Patterns for field detection
        self.field_patterns = {
            "Tipo": re.compile(r"^(?:Tipo|Type):?\s*(.*)", re.IGNORECASE),
            "Objetivo": re.compile(r"^(?:Objetivo|Objective):?\s*(.*)", re.IGNORECASE),
            "Descripción": re.compile(r"^(?:Descripción|Description):?\s*(.*)", re.IGNORECASE),
            "Alcance": re.compile(r"^(?:Alcance funcional esperado|Alcance|Scope|Functional Scope):?\s*(.*)", re.IGNORECASE),
            "Criterios": re.compile(r"^(?:Criterios de aceptación|Criterios|Criteria|Acceptance Criteria):?\s*(.*)", re.IGNORECASE),
            "Dependencias": re.compile(r"^(?:Dependencias|Dependencies):?\s*(.*)", re.IGNORECASE),
        }
        self.issue_start_pattern = re.compile(r"^(\d+)\)\s+(.*)")
        self.bullet_pattern = re.compile(r"^[●•-]\s*(.*)")
        self.dynamic_header_pattern = re.compile(r"^([A-ZáéíóúÁÉÍÓÚñÑ][^.]{3,60})$")

    def from_pdf(self, pdf_path):
        """Extracts text from PDF and parses it into a list of issue objects."""
        full_text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        
        return self.parse_text(full_text)

    def parse_text(self, text):
        """Segments text into blocks and parses each block."""
        lines = text.splitlines()
        issues = []
        current_issue = None
        current_field = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for issue start
            match_start = self.issue_start_pattern.match(line)
            if match_start:
                if current_issue:
                    issues.append(self._finalize_issue(current_issue))
                
                current_issue = {
                    "number": match_start.group(1),
                    "title": match_start.group(2),
                    "Tipo": "",
                    "Objetivo": "",
                    "Descripción": "",
                    "Alcance": "",
                    "Criterios": "",
                    "Dependencias": "",
                    "dynamic_fields": {},
                    "extra": []
                }
                self.custom_order = [] # To preserve order of appearance
                current_field = "title"
                continue

            if not current_issue:
                continue

            # 2. Check for known field change
            field_matched = False
            for field_name, pattern in self.field_patterns.items():
                match_field = pattern.match(line)
                if match_field:
                    current_field = field_name
                    val = match_field.group(1).strip()
                    if val:
                        current_issue[field_name] = val
                    field_matched = True
                    break
            
            if field_matched:
                continue

            # 3. Check for potential dynamic header BEFORE accumulating content
            match_dyn = self.dynamic_header_pattern.match(line)
            # A line is a header if it matches the pattern AND (is short OR lacks punctuation)
            # To avoid false positives, we check if it's not a known field and if it's not a bullet
            is_bullet = self.bullet_pattern.match(line)
            if match_dyn and not is_bullet:
                h_name = match_dyn.group(1).strip()
                # Create dynamic field if not exists (or switch to it)
                if h_name not in current_issue["dynamic_fields"]:
                    current_issue["dynamic_fields"][h_name] = ""
                    self.custom_order.append(h_name)
                current_field = h_name
                continue

            # 4. Handle content based on current state
            if current_field == "title":
                current_issue["title"] += " " + line
            elif current_field in ["Objetivo", "Descripción", "Alcance", "Criterios", "Dependencias"] or current_field in current_issue.get("dynamic_fields", {}):
                bullet_match = self.bullet_pattern.match(line)
                if bullet_match:
                    content = "\n- " + bullet_match.group(1).strip()
                    if current_field in current_issue["dynamic_fields"]:
                        current_issue["dynamic_fields"][current_field] += content
                    else:
                        current_issue[current_field] += content
                else:
                    target = current_issue["dynamic_fields"] if current_field in current_issue["dynamic_fields"] else current_issue
                    if target[current_field].endswith("- "):
                         target[current_field] += line
                    else:
                         target[current_field] += (" " if target[current_field] else "") + line
            else:
                current_issue["extra"].append(line)

        if current_issue:
            issues.append(self._finalize_issue(current_issue))

        return issues

    def _finalize_issue(self, data):
        """Converts raw extracted data into the final GitLab structure."""
        title = data["title"].strip()
        tipo = data["Tipo"].strip()
        
        labels = []
        if tipo:
            labels.append(tipo)
        
        description_parts = []
        
        if data["Objetivo"]:
            description_parts.append(f"## Objetivo\n{data['Objetivo'].strip()}")
        
        if data["Descripción"]:
            description_parts.append(f"## Descripción\n{data['Descripción'].strip()}")
            
        if data["Alcance"]:
            description_parts.append(f"## Alcance\n{data['Alcance'].strip()}")
            
        if data["Criterios"]:
            description_parts.append(f"## Criterios de Aceptación\n{data['Criterios'].strip()}")

        # Dynamic fields in order
        for field in self.custom_order:
            val = data["dynamic_fields"].get(field, "").strip()
            if val:
                description_parts.append(f"## {field}\n{val}")
            
        if data["Dependencias"]:
            description_parts.append(f"## Dependencias\n{data['Dependencias'].strip()}")

        final_description = "\n\n".join(description_parts)

        return {
            "issue_data": {
                "title": title,
                "description": final_description,
                "labels": labels,
                "attributes": {
                    "weight": None,
                    "milestone_id": None
                }
            }
        }

    def save_to_json(self, issues, output_path):
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(issues, f, indent=2, ensure_ascii=False)
