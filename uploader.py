import os
import json
import gitlab
from dotenv import load_dotenv

class GitLabUploader:
    def __init__(self, env_path="config.env"):
        load_dotenv(env_path)
        self.url = os.getenv("GITLAB_URL")
        self.token = os.getenv("GITLAB_TOKEN")
        self.project_id = os.getenv("PROJECT_ID")
        
        if not all([self.url, self.token, self.project_id]):
            raise ValueError("Faltan variables de entorno en config.env (GITLAB_URL, GITLAB_TOKEN, PROJECT_ID)")

        self.gl = gitlab.Gitlab(self.url, private_token=self.token)
        self.project = self.gl.projects.get(self.project_id)

    def get_milestones(self):
        """Fetches active milestones from the project."""
        return self.project.milestones.list(state='active')

    def get_members(self):
        """Fetches project members."""
        # all=True ensures we get members even if inherited from groups
        return self.project.members.list(all=True)

    def ensure_labels(self, labels_string, color="#FF0000"):
        """Ensures that the global labels exist in the project with the specified color."""
        if not labels_string:
            return []
        
        names = [n.strip() for n in labels_string.split(",") if n.strip()]
        for name in names:
            try:
                # Check if label exists and update color if needed
                lbl = self.project.labels.get(name)
                if lbl.color.upper() != color.upper():
                    lbl.color = color
                    lbl.save()
                    print(f"🎨 Color de etiqueta actualizado: {name} -> {color}")
            except:
                # Create if not exists
                try:
                    self.project.labels.create({'name': name, 'color': color})
                    print(f"🏷️ Etiqueta creada: {name} ({color})")
                except Exception as e:
                    print(f"⚠️ Error al crear etiqueta {name}: {e}")
        return names

    def upload_from_json(self, json_path, global_labels=None, label_color="#FF0000", milestone_id=None, start_date=None, due_date=None, assignee_id=None):
        """Reads JSON file and creates issues in GitLab with optional global metadata."""
        if not os.path.exists(json_path):
            print(f"Error: El archivo {json_path} no existe.")
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            issues = json.load(f)

        # Ensure global labels exist
        extra_label_names = self.ensure_labels(global_labels, label_color)

        print(f"Iniciando carga de {len(issues)} issues en el proyecto {self.project.name}...")
        
        for entry in issues:
            issue_data = entry.get("issue_data")
            if not issue_data:
                continue
            
            title = issue_data.get("title")
            # Inject Quick Actions into the initial description to let GitLab's internal parser handle dates
            description = issue_data.get("description", "")
            if start_date: description += f"\n\n/start_date {start_date}"
            if due_date: description += f"\n\n/due_date {due_date}"
            
            labels = issue_data.get("labels", [])
            labels.extend(extra_label_names)
            
            try:
                # Create issue
                payload = {
                    'title': title,
                    'description': description,
                    'labels': list(set(labels)), # Unique labels
                    'weight': issue_data.get("attributes", {}).get("weight"),
                    'milestone_id': milestone_id or issue_data.get("attributes", {}).get("milestone_id"),
                    'start_date': start_date,
                    'due_date': due_date,
                    'assignee_id': assignee_id or issue_data.get("attributes", {}).get("assignee_id")
                }
                
                new_issue = self.project.issues.create(payload)
                
                # Ultimate Date Sync via GraphQL (GitLab 16+)
                if start_date or due_date:
                    try:
                        # Direct GraphQL call via HTTP POST (Compatibility for older python-gitlab)
                        project_path = self.project.path_with_namespace
                        
                        # 1. Introspection: Get GID and then available widgets (Two-step for compatibility)
                        query_gid = """
                        query($fullPath: ID!, $iid: String!) {
                          project(fullPath: $fullPath) {
                            issue(iid: $iid) { id }
                          }
                        }
                        """
                        # Correct GraphQL endpoint for GitLab.com
                        graphql_url = f"{self.url.rstrip('/')}/api/graphql"
                        headers = {'PRIVATE-TOKEN': self.token}
                        
                        # Step A: Get Global ID
                        res_gid_raw = self.gl.session.post(graphql_url, json={
                            'query': query_gid, 
                            'variables': {"fullPath": project_path, "iid": str(new_issue.iid)}
                        }, headers=headers)
                        gid_data = res_gid_raw.json()
                        gid = gid_data.get('data', {}).get('project', {}).get('issue', {}).get('id')
                        
                        widgets = []
                        if gid:
                            gid_wi = gid.replace("Issue", "WorkItem")
                            query_widgets = """
                            query($id: WorkItemID!) {
                              workItem(id: $id) {
                                widgets { type }
                              }
                            }
                            """
                            res_w_raw = self.gl.session.post(graphql_url, json={
                                'query': query_widgets, 
                                'variables': {"id": gid_wi}
                            }, headers=headers)
                            w_data = res_w_raw.json()
                            widgets = [w.get('type') for w in w_data.get('data', {}).get('workItem', {}).get('widgets', [])]
                        
                        if gid:
                            # 2. Update via GraphQL if widgets exist
                            # Determine widget name dynamically
                            widget_name = None
                            if 'START_AND_DUE_DATE' in widgets:
                                widget_name = 'startAndDueDateWidget'
                            elif 'DATES' in widgets:
                                widget_name = 'datesWidget'
                            
                            if widget_name:
                                gid_workitem = gid.replace("Issue", "WorkItem")
                                mutation = f"""
                                mutation($id: WorkItemID!, $startDate: Date, $dueDate: Date) {{
                                  workItemUpdate(input: {{
                                    id: $id,
                                    {widget_name}: {{
                                      startDate: $startDate,
                                      dueDate: $dueDate,
                                      isFixed: true
                                    }}
                                  }}) {{
                                    errors
                                  }}
                                }}
                                """
                                variables = {
                                    "id": gid_workitem,
                                    "startDate": start_date if start_date else None,
                                    "dueDate": due_date if due_date else None
                                }
                                m_res_raw = self.gl.session.post(graphql_url, json={'query': mutation, 'variables': variables}, headers=headers)
                                m_res = m_res_raw.json()
                                errors = m_res.get('data', {}).get('workItemUpdate', {}).get('errors', [])
                                if errors:
                                    # Silent fail to avoid polluting console, but could log to file if needed
                                    pass
                            
                        # Redundant Backup: Always try Quick Actions too
                        try:
                            qa_body = []
                            if start_date: qa_body.append(f"/start_date {start_date}")
                            if due_date: qa_body.append(f"/due_date {due_date}")
                            if qa_body:
                                self.project.issues.get(new_issue.iid).notes.create({'body': "\n".join(qa_body)})
                        except Exception as e:
                            # print(f"⚠️ Error en Quick Action Note: {e}")
                            pass

                    except Exception as e:
                        print(f"⚠️ Error fatal en sync de fechas: {e}")
                
                print(f"✅ Éxito: '{title}' -> {new_issue.web_url}")
            except Exception as e:
                print(f"❌ Error al crear '{title}': {str(e)}")

if __name__ == "__main__":
    # Test quickly if run directly
    try:
        uploader = GitLabUploader()
        print(f"Conectado a: {uploader.url}")
    except Exception as e:
        print(f"Error de conexión: {e}")
