# sync_xml_from_drive.py actualizado para usar xml_processor.py
import os
import io
import frappe
import json
from frappe.utils import now
from frappe.utils.file_manager import get_file
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from datetime import datetime, timedelta
from erpnext_chile_factura.erpnext_chile_sii_integration.utils.xml_processor import procesar_xml_content


def get_mes_actual_y_anterior():
    today = datetime.today()
    mes_actual = today.strftime("%Y-%m")
    primer_dia_mes_actual = today.replace(day=1)
    ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
    mes_anterior = ultimo_dia_mes_anterior.strftime("%Y-%m")
    return [mes_anterior, mes_actual]


def encontrar_subcarpeta(drive_service, parent_id, nombre):
    resultado = drive_service.files().list(
        q=f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and name = '{nombre}'",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    carpetas = resultado.get("files", [])
    return carpetas[0]["id"] if carpetas else None


def listar_archivos_en_carpeta(drive_service, folder_id):
    resultado = drive_service.files().list(
        q=f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder'",
        fields="files(id, name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    return [f for f in resultado.get("files", []) if f["name"].lower().endswith(".xml")]


def mover_archivo_a_procesados(drive_service, file_id, id_recibidos, subcarpeta=None):
    id_procesados = encontrar_subcarpeta(
        drive_service, id_recibidos, "procesados")
    if not id_procesados:
        id_procesados = drive_service.files().create(
            body={"name": "procesados", "mimeType": "application/vnd.google-apps.folder",
                  "parents": [id_recibidos]},
            fields="id",
            supportsAllDrives=True
        ).execute()["id"]

    destino_id = id_procesados

    if subcarpeta:
        id_sub = encontrar_subcarpeta(drive_service, id_procesados, subcarpeta)
        if not id_sub:
            id_sub = drive_service.files().create(
                body={"name": subcarpeta, "mimeType": "application/vnd.google-apps.folder",
                      "parents": [id_procesados]},
                fields="id",
                supportsAllDrives=True
            ).execute()["id"]
        destino_id = id_sub

    file_metadata = drive_service.files().get(fileId=file_id, fields='parents',
                                              supportsAllDrives=True).execute()
    padres_actuales = ",".join(file_metadata.get("parents", []))

    drive_service.files().update(
        fileId=file_id,
        addParents=destino_id,
        removeParents=padres_actuales,
        supportsAllDrives=True
    ).execute()


def sync_xml_from_drive():
    logger = frappe.logger("sii_drive_sync")
    logger.info("Inicio sincronización de XML desde Google Drive (uno a uno)")

    configs = frappe.get_all(
        "SII Google Drive Sync Config", fields=["name", "company"])
    for config in configs:
        doc = frappe.get_doc("SII Google Drive Sync Config", config.name)

        if not doc.gdrive_credentials_file:
            logger.warning(
                f"Empresa {doc.company} no tiene archivo de credenciales configurado.")
            continue

        try:
            file_name, file_content = get_file(doc.gdrive_credentials_file)
            credentials_dict = json.loads(file_content)
            creds = service_account.Credentials.from_service_account_info(
                credentials_dict, scopes=[
                    "https://www.googleapis.com/auth/drive"]
            )
            drive_service = build("drive", "v3", credentials=creds)
        except Exception as e:
            logger.error(
                f"Error al cargar credenciales para {doc.company}: {str(e)}")
            continue

        for carpeta in doc.carpetas_drive:
            if not carpeta.activa or carpeta.tipo_sincronizacion != "XML Preinvoice":
                continue

            try:
                for mes in get_mes_actual_y_anterior():
                    id_mes = encontrar_subcarpeta(
                        drive_service, carpeta.id_carpeta_drive, mes)
                    if not id_mes:
                        continue

                    id_recibidos = encontrar_subcarpeta(
                        drive_service, id_mes, "recibidos")
                    if not id_recibidos:
                        continue

                    archivos = listar_archivos_en_carpeta(
                        drive_service, id_recibidos)
                    logger.info(
                        f"Procesando {len(archivos)} XML para {doc.company} en {mes}")

                    for file in archivos:
                        try:
                            fh = io.BytesIO()
                            request = drive_service.files().get_media(
                                fileId=file["id"], supportsAllDrives=True)
                            downloader = MediaIoBaseDownload(fh, request)
                            done = False
                            while not done:
                                _, done = downloader.next_chunk()
                            xml_content = fh.getvalue()

                            mensaje = procesar_xml_content(
                                xml_content, file["name"])
                            logger.info(mensaje)

                            if "correctamente" in mensaje:
                                mover_archivo_a_procesados(
                                    drive_service, file["id"], id_recibidos)
                            elif "Guía" in mensaje:
                                mover_archivo_a_procesados(
                                    drive_service, file["id"], id_recibidos, subcarpeta="guias")

                        except Exception as e:
                            logger.error(
                                f"{file['name']}: Error al procesar: {str(e)}")

            except Exception as e:
                logger.error(
                    f"Error al procesar empresa {doc.company} - carpeta {carpeta.id_carpeta_drive}: {str(e)}")
