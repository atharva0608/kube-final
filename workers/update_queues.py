import os

workers_dir = '/Users/atharvapudale/Desktop/backend-ecc/Atharva Repo/github/balancekube/workers'

for dirname in os.listdir(workers_dir):
    dir_path = os.path.join(workers_dir, dirname)
    if os.path.isdir(dir_path) and dirname != 'common':
        md_file = os.path.join(dir_path, f"{dirname}.md")
        if os.path.exists(md_file):
            with open(md_file, 'r') as f:
                content = f.read()
            
            if 'queue:' not in content:
                # Find ## Inputs and append the queue
                parts = content.split('## Inputs\n')
                if len(parts) == 2:
                    new_content = parts[0] + f"## Inputs\n- Queue: `queue:{dirname}`\n" + parts[1]
                    with open(md_file, 'w') as f:
                        f.write(new_content)
                    print(f"Updated {dirname}.md")
                else:
                    print(f"Could not find ## Inputs in {dirname}.md")

