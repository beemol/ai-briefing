import csv
import json
import os


def extract_schema(csv_path: str, output_path: str):
    schema = {}
    with open(csv_path, mode='r', encoding='utf-8') as f:
        # Skip the first line "Table 1"
        _ = f.readline()
        reader = csv.DictReader(f)
        for row in reader:
            table = row['[Table]']
            column = row['[Column]']
            data_type = row['[DataType]']
            is_hidden = row['[IsHidden]'].lower() == 'true'
            
            # Skip hidden tables/columns and internal Power BI tables
            if is_hidden:
                continue
            if table.startswith(('LocalDateTable_', 'DateTableTemplate_')):
                continue
                
            if table not in schema:
                schema[table] = []
            
            schema[table].append({
                "name": column,
                "type": data_type
            })
            
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    
    print(f"Schema extracted to {output_path}")

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    extract_schema(
        os.path.join(base, "powerbi_schema.csv"),
        os.path.join(base, "powerbi_schema.json"),
    )
