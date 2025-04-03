# Librerías importadas
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
from datetime import datetime
import os

# Instancia de FastAPI
app = FastAPI()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NUM_PUESTOS = 20  # Total de puestos disponibles
TARIFA_POR_INGRESO = 0  # Tarifa

# Función para obtener la conexión a la base de datos
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.environ.get("DB_HOST"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            database=os.environ.get("DB_NAME"),
            port=int(os.environ.get("DB_PORT"))
        )
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {err}")



@app.post("/validar_placa/")
def validar_placa(data: dict):
    placa = data.get("placa")
    if not placa:
        raise HTTPException(status_code=400, detail="Placa no proporcionada")

    placa = placa.replace("-", "")  # Ignorar el carácter "-"

    mydb = get_db_connection()
    cursor = mydb.cursor(dictionary=True)

    try:
        # Buscar documento del vehículo
        cursor.execute("SELECT documento FROM vehiculos WHERE REPLACE(placa, '-', '') = %s", (placa,))
        vehiculo = cursor.fetchone()

        if not vehiculo or not vehiculo["documento"]:
            return {"mensaje": "Vehículo no registrado", "permitido": False}

        documento = vehiculo["documento"]

        # Verificar si el documento existe en beneficiarios
        cursor.execute("SELECT * FROM beneficiarios WHERE documento = %s", (documento,))
        beneficiario = cursor.fetchone()

        if not beneficiario:
            return {"mensaje": "Documento no registrado", "permitido": False}

        # Buscar si el vehículo ya tiene un ingreso sin salida
        cursor.execute("SELECT * FROM registros WHERE placa = %s AND estado = 'ingreso' ORDER BY fecha_ingreso DESC LIMIT 1", (placa,))
        registro = cursor.fetchone()

        if registro:
            # Si ya ingresó, marcar salida
            cursor.execute("UPDATE registros SET estado = 'salida', fecha_salida = %s WHERE id = %s",
                        (datetime.now(), registro["id"]))
            mydb.commit()
            return {"mensaje": f"Salida confirmada para {placa}", "permitido": True, "salida": True, "puesto": registro["puesto"]}

        # Contar puestos ocupados
        cursor.execute("SELECT COUNT(*) as ocupados FROM registros WHERE estado = 'ingreso'")
        ocupados = cursor.fetchone()["ocupados"]

        if ocupados >= NUM_PUESTOS:
            return {"mensaje": "No hay puestos disponibles", "permitido": False}

        # Asignar el siguiente puesto disponible
        puesto_asignado = ocupados + 1

        # Registrar el ingreso con puesto y tarifa
        cursor.execute("INSERT INTO registros (placa, documento, estado, fecha_ingreso, puesto, valor_parqueo) VALUES (%s, %s, %s, %s, %s, %s)",
                    (placa, documento, "ingreso", datetime.now(), puesto_asignado, TARIFA_POR_INGRESO))
        mydb.commit()

        return {"mensaje": f"Ingreso registrado para {placa}", "permitido": True, "salida": False, "puesto": puesto_asignado}

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Error en la base de datos: {err}")

    finally:
        cursor.close()
        mydb.close()
