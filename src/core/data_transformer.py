import re
import logging
from typing import List, Dict, Union, Optional

class DataTransformer:
    @staticmethod
    def clean_numeric_string(value: str) -> Union[float, str]:
        """Convert '€ 1.234,56', '1,85', '10%', etc. to float if possible."""
        if not value or not isinstance(value, str):
            return value
            
        # 1. Clean common betting symbols and spaces
        # Remove: Currency (€ $ £), Percent (%), Commas (if used for decimals), Dots (if used for thousands)
        # Note: This needs to be careful because some regions use '.' for decimals and ',' for thousands, or vice-versa.
        # Most betting sites use '.' for decimals or ',' for decimals.
        
        orig_value = value.strip()
        
        # Remove currency symbols and other non-numeric chars (except decimal points/commas/minus)
        cleaned = re.sub(r'[^\d,.\-]', '', orig_value)
        
        if not cleaned:
            return orig_value
            
        try:
            # Handle cases with both '.' and ',' 
            # Example: '1.234,56' (European) -> 1234.56
            if ',' in cleaned and '.' in cleaned:
                # Assume the last one is the decimal separator
                if cleaned.find(',') > cleaned.find('.'):
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            # Example: '1,85' -> 1.85
            elif ',' in cleaned:
                # If there's only one comma, it's likely a decimal separator
                cleaned = cleaned.replace(',', '.')
            
            # Final attempt to convert to float
            return float(cleaned)
        except ValueError:
            return orig_value

    @staticmethod
    def transform_table_to_dicts(table_rows: List[List[str]]) -> List[Dict[str, Union[float, str]]]:
        """Transform a list of lists (table) into a list of dicts with cleaned numeric values."""
        if not table_rows or len(table_rows) < 2:
            return []
            
        headers = [h.strip() for h in table_rows[0]]
        results = []
        
        # Common separators for columns that might contain multiple data points
        separators = [r' / ', r' \| ', r'\n', r' - '] 
        
        for row in table_rows[1:]:
            row_padded = (row + [""] * len(headers))[:len(headers)]
            row_dict = {}
            for i, header in enumerate(headers):
                if not header:
                    header = f"column_{i}"
                
                raw_value = row_padded[i].strip()
                
                # SPECIAL HANDLING FOR EXCAPPER COLUMNS
                if header.lower() == "change" and " / " in raw_value:
                    parts = raw_value.split(" / ")
                    row_dict["Change_Amount"] = DataTransformer.clean_numeric_string(parts[0])
                    row_dict["Change_Percent"] = DataTransformer.clean_numeric_string(parts[1])
                elif header.lower() == "score" and "-" in raw_value:
                    parts = raw_value.split("-")
                    row_dict["Score_Home"] = DataTransformer.clean_numeric_string(parts[0])
                    row_dict["Score_Away"] = DataTransformer.clean_numeric_string(parts[1])
                else:
                    # Generic Splitting Logic
                    parts = []
                    for sep in separators:
                        if re.search(sep, raw_value):
                            parts = [p.strip() for p in re.split(sep, raw_value) if p.strip()]
                            break
                    
                    if len(parts) > 1:
                        for idx, part in enumerate(parts):
                            row_dict[f"{header}_{idx+1}"] = DataTransformer.clean_numeric_string(part)
                    else:
                        row_dict[header] = DataTransformer.clean_numeric_string(raw_value)
                
                # Always keep original for reference
                if header not in row_dict:
                    row_dict[header] = raw_value
                
            results.append(row_dict)
            
        return results

    @classmethod
    def process_match_notification(cls, match_data: Dict[str, List[List[str]]]) -> Dict[str, List[Dict[str, Union[float, str]]]]:
        """Process all tables in match_data and return a numeric-friendly dictionary."""
        cleaned_tables = {}
        
        for table_id, rows in match_data.items():
            if rows:
                cleaned_tables[table_id] = cls.transform_table_to_dicts(rows)
                
        return cleaned_tables
