import os

def print_important_files():
    # Define file groups with their paths
    file_groups = {
        'Core Application': [
            'app/main.py',
            'app/__init__.py',
            'app/models/models.py',
            'app/schemas/project.py'
        ],
        'Data Collectors': [
            'app/services/data_collectors/lansstyrelsen_collector.py',
            'app/services/data_collectors/lansstyrelsen.py'
        ],
        'API Routes': [
            'app/routers/projects.py',
            'app/routers/categorization.py'
        ],
        'Tests': [
            'tests/test_api.py',
            'tests/test_lansstyrelsen_collector.py',
            'tests/test_api_integration.py'
        ],
        'Configuration': [
            'README.md',
            'requirements.txt',
            'requirements-dev.txt',
            'alembic.ini',
            'pytest.ini'
        ],
        'Documentation': [
            'docs/lansstyrelsen_collector.md',
            'docs/green_industrial_filtering.md'
        ]
    }
    
    base_dir = os.getcwd()
    
    for group, files in file_groups.items():
        print(f"\n## {group}")
        for file_path in files:
            full_path = os.path.join(base_dir, file_path)
            try:
                with open(full_path, 'r') as f:
                    content = f.read().strip()
                    file_ext = os.path.splitext(file_path)[1][1:] or 'txt'
                    print(f"\n```{file_ext}:{file_path}\n{content}\n```\n")
            except FileNotFoundError:
                print(f"File not found: {file_path}")
            except Exception as e:
                print(f"Error reading {file_path}: {str(e)}")

if __name__ == "__main__":
    print_important_files()