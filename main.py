import argparse
import sys
import os
from parser import IssueParser
from uploader import GitLabUploader
import questionary
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

def print_banner(text):
    print(f"\n{Style.BRIGHT}{Fore.CYAN}{'='*len(text)}")
    print(f"{Style.BRIGHT}{Fore.CYAN}{text}")
    print(f"{Style.BRIGHT}{Fore.CYAN}{'='*len(text)}\n")

def print_success(text):
    print(f"{Fore.GREEN}✅ {text}")

def print_error(text):
    print(f"{Fore.RED}❌ {text}")

def print_warning(text):
    print(f"{Fore.YELLOW}⚠️ {text}")

def main():
    parser = argparse.ArgumentParser(
        description="GitLab Issue Provisioner - herramientas para automatizar la creación de issues desde PDF."
    )
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Comando parse
    parser_cmd = subparsers.add_parser("parse", help="Extrae issues de un archivo PDF y genera un JSON.")
    parser_cmd.add_argument("pdf_path", help="Ruta al archivo PDF de origen.")
    parser_cmd.add_argument("-o", "--output", default="extracted_issues.json", help="Nombre del archivo JSON de salida.")

    # Comando upload
    upload_cmd = subparsers.add_parser("upload", help="Sube las issues desde un archivo JSON a GitLab.")
    upload_cmd.add_argument("json_path", help="Ruta al archivo JSON con los datos de las issues.")
    upload_cmd.add_argument("-e", "--env", default="config.env", help="Ruta al archivo de configuración .env.")

    args = parser.parse_args()

    if args.command == "parse":
        try:
            print_banner("FASE DE EXTRACCIÓN")
            print(f"Procesando: {Fore.BLUE}{args.pdf_path}")
            
            parser_obj = IssueParser()
            issues = parser_obj.from_pdf(args.pdf_path)
            
            # --- Visual Report of Detected Labels ---
            print(f"\n{Style.BRIGHT}Resumen de Extracción:")
            print(f"{Fore.CYAN}{'-'*60}")
            print(f"{Style.BRIGHT}{'#':<3} | {'Título del Issue':<40} | {'Etiquetas'}")
            print(f"{Fore.CYAN}{'-'*60}")
            
            for i, entry in enumerate(issues, 1):
                title = entry['issue_data']['title']
                # Truncate title if too long
                display_title = (title[:37] + '...') if len(title) > 40 else title
                labels = ", ".join(entry['issue_data']['labels']) if entry['issue_data']['labels'] else "Ninguna"
                print(f"{i:<3} | {display_title:<40} | {Fore.YELLOW}{labels}")
            print(f"{Fore.CYAN}{'-'*60}\n")
            
            parser_obj.save_to_json(issues, args.output)
            print_success(f"Extracción completada. {len(issues)} issues guardadas en '{args.output}'.")
            print(f"Por favor, revise el archivo JSON antes de subirlo.")
        except Exception as e:
            print_error(f"Error durante el parsing: {e}")
            sys.exit(1)

    elif args.command == "upload":
        try:
            print_banner("FASE DE CARGA A GITLAB")
            uploader = GitLabUploader(env_path=args.env)
            
            # --- Navegación de Proyectos/Grupos ---
            initial_id = uploader.project_id
            target_project = uploader.get_project(initial_id)
            
            if not target_project:
                group = uploader.get_group(initial_id)
                if group:
                    print_warning(f"ID '{initial_id}' detectado como Grupo. Iniciando navegación...")
                    history = []
                    current_group = group
                    
                    while True:
                        subgroups, projects = uploader.get_group_contents(current_group)
                        choices = []
                        if history:
                            choices.append(questionary.Choice("⬅️  .. (Volver atrás)", value="BACK"))
                        
                        for sg in subgroups:
                            choices.append(questionary.Choice(f"📁 [Grupo] {sg.name}", value=("GROUP", sg.id)))
                        
                        for p in projects:
                            choices.append(questionary.Choice(f"🚀 [Proyecto] {p.name}", value=("PROJECT", p.id)))
                        
                        if not choices:
                            print_error("Este grupo está vacío (sin proyectos ni subgrupos).")
                            sys.exit(1)
                            
                        selection = questionary.select(
                            f"📁 Grupo: {current_group.full_name}. Seleccione:",
                            choices=choices
                        ).ask()
                        
                        if selection is None:
                            print_error("Operación cancelada.")
                            sys.exit(0)
                        
                        if selection == "BACK":
                            current_group = history.pop()
                        elif selection[0] == "GROUP":
                            history.append(current_group)
                            current_group = uploader.gl.groups.get(selection[1])
                        elif selection[0] == "PROJECT":
                            target_project = uploader.gl.projects.get(selection[1])
                            break
                else:
                    print_error(f"No se encontró Proyecto ni Grupo con ID: {initial_id}")
                    sys.exit(1)

            uploader.set_project(target_project)
            print_success(f"Conectado al proyecto: {Style.BRIGHT}{target_project.name_with_namespace}")

            # --- Interacción para Metadata Global ---
            print(f"{Style.BRIGHT}Configuración opcional para todas las issues:\n")
            
            # 1. Etiquetas globales
            all_labels_to_apply = []
            
            # Step 1.1: Existing labels selection
            existing_labels = []
            try:
                existing_labels = uploader.get_labels()
                if existing_labels:
                    label_names = [lb.name for lb in existing_labels]
                    choices = questionary.checkbox(
                        "Seleccione etiquetas existentes para aplicar a todas las issues:",
                        choices=label_names
                    ).ask()
                    if choices:
                        all_labels_to_apply.extend(choices)
            except Exception as e:
                print_warning(f"No se pudieron obtener las etiquetas existentes: {e}")

            # Step 1.2: New labels interactive creation
            existing_names_set = {lb.name.lower() for lb in existing_labels} if existing_labels else set()
            
            print(f"\n{Fore.CYAN}Creación de nuevas etiquetas (opcional):")
            while True:
                new_lb_name = questionary.text("Nombre de nueva etiqueta (vacío para terminar):").ask()
                if not new_lb_name:
                    break
                
                new_lb_name = new_lb_name.strip()
                if new_lb_name.lower() in existing_names_set:
                    print_error(f"La etiqueta '{new_lb_name}' ya existe en el proyecto.")
                    continue
                
                new_lb_color = questionary.text(
                    f"Color para '{new_lb_name}' (HEX, ej: #FF0000):",
                    default="#FF0000"
                ).ask() or "#FF0000"
                
                if not new_lb_color.startswith("#"):
                    new_lb_color = "#" + new_lb_color

                try:
                    uploader.ensure_labels([new_lb_name], color=new_lb_color)
                    all_labels_to_apply.append(new_lb_name)
                    existing_names_set.add(new_lb_name.lower())
                    print_success(f"Etiqueta '{new_lb_name}' registrada.")
                except Exception as e:
                    print_error(f"Error al crear la etiqueta: {e}")

            # 2. Milestones
            selected_milestone_id = None
            try:
                milestones = uploader.get_milestones()
                if milestones:
                    m_choices = ["Ninguno"] + [f"{m.title} (ID: {m.id})" for m in milestones]
                    m_selection = questionary.select(
                        "Seleccione un milestone:",
                        choices=m_choices
                    ).ask()
                    
                    if m_selection != "Ninguno":
                        idx = m_choices.index(m_selection) - 1
                        selected_milestone_id = milestones[idx].id
                        print_success(f"Milestone asignado: {milestones[idx].title}")
            except Exception as e:
                print_warning(f"No se pudieron obtener los milestones: {e}")

            # 3. Members / Assignee
            selected_assignee_id = None
            try:
                members = uploader.get_members()
                if members:
                    member_choices = ["Ninguno"] + [f"{m.name if hasattr(m, 'name') else m.username} (@{m.username})" for m in members]
                    member_selection = questionary.select(
                        "¿Deseas asignar estas historias a alguien?",
                        choices=member_choices
                    ).ask()
                    
                    if member_selection != "Ninguno":
                        idx = member_choices.index(member_selection) - 1
                        selected_assignee_id = members[idx].id
                        print_success(f"Asignado a: {members[idx].name if hasattr(members[idx], 'name') else members[idx].username}")
            except Exception as e:
                print_warning(f"No se pudieron obtener los miembros: {e}")

            # 4. Fechas
            print(f"\n{Fore.CYAN}Configuración de fechas (YYYY-MM-DD):")
            s_date = questionary.text("Fecha de inicio (opcional):").ask()
            d_date = questionary.text("Fecha límite (opcional):").ask()

            print_banner("INICIANDO CARGA")
            uploader.upload_from_json(
                args.json_path, 
                global_labels=all_labels_to_apply, 
                milestone_id=selected_milestone_id,
                start_date=s_date if s_date else None,
                due_date=d_date if d_date else None,
                assignee_id=selected_assignee_id
            )
        except Exception as e:
            print_error(f"Error durante la carga: {e}")
            sys.exit(1)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
