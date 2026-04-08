import argparse
import sys
from parser import IssueParser
from uploader import GitLabUploader

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
            print(f"--- FASE DE EXTRACCIÓN ---")
            print(f"Procesando: {args.pdf_path}")
            parser_obj = IssueParser()
            issues = parser_obj.from_pdf(args.pdf_path)
            parser_obj.save_to_json(issues, args.output)
            print(f"✅ Extracción completada. {len(issues)} issues guardadas en '{args.output}'.")
            print(f"Por favor, revise el archivo JSON antes de subirlo.")
        except Exception as e:
            print(f"❌ Error durante el parsing: {e}")
            sys.exit(1)

    elif args.command == "upload":
        try:
            print(f"--- FASE DE CARGA A GITLAB ---")
            uploader = GitLabUploader(env_path=args.env)
            
            # --- Interacción para Metadata Global ---
            print("\nConfiguración opcional para todas las issues:")
            
            # 1. Etiquetas globales
            g_labels = input("Etiquetas adicionales (separadas por coma, ej: Sprint-2, Frontend) [Enter para omitir]: ").strip()
            g_color = "#FF0000"
            if g_labels:
                g_color = input("Color para estas etiquetas (HEX, ej: #FF0000) [#FF0000]: ").strip() or "#FF0000"
            
            # 2. Milestones
            selected_milestone_id = None
            try:
                milestones = uploader.get_milestones()
                if milestones:
                    print("\nMilestones activos encontrados:")
                    print("0) Ninguno")
                    for i, m in enumerate(milestones, 1):
                        print(f"{i}) {m.title} (ID: {m.id})")
                    
                    choice = input(f"\nSeleccione un milestone (0-{len(milestones)}) [0]: ").strip()
                    if choice and choice.isdigit() and 1 <= int(choice) <= len(milestones):
                        selected_milestone_id = milestones[int(choice)-1].id
                        print(f"Asignando milestone: {milestones[int(choice)-1].title}")
            except Exception as e:
                print(f"⚠️ No se pudieron obtener los milestones: {e}")

            # 3. Members / Assignee
            selected_assignee_id = None
            try:
                members = uploader.get_members()
                if members:
                    print("\nMiembros del proyecto encontrados:")
                    print("0) Ninguno")
                    for i, m in enumerate(members, 1):
                        display_name = m.name if hasattr(m, 'name') else m.username
                        print(f"{i}) {display_name} (@{m.username})")
                    
                    m_choice = input(f"\n¿Deseas asignar estas historias a alguien? (0-{len(members)}) [0]: ").strip()
                    if m_choice and m_choice.isdigit() and 1 <= int(m_choice) <= len(members):
                        selected_assignee_id = members[int(m_choice)-1].id
                        print(f"Asignando a: {members[int(m_choice)-1].name}")
            except Exception as e:
                print(f"⚠️ No se pudieron obtener los miembros: {e}")

            # 4. Fechas
            print("\nConfiguración de fechas (formato YYYY-MM-DD):")
            s_date = input("Fecha de inicio [Enter para omitir]: ").strip()
            d_date = input("Fecha límite (Due Date) [Enter para omitir]: ").strip()

            print("\n--- Iniciando carga ---")
            uploader.upload_from_json(
                args.json_path, 
                global_labels=g_labels, 
                label_color=g_color,
                milestone_id=selected_milestone_id,
                start_date=s_date if s_date else None,
                due_date=d_date if d_date else None,
                assignee_id=selected_assignee_id
            )
        except Exception as e:
            print(f"❌ Error durante la carga: {e}")
            sys.exit(1)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
