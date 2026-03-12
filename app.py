from flask import Flask, render_template, request, jsonify, redirect
import sqlite3
import threading
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import json
import random

app = Flask(__name__)
DB = "restaurante.db"
load_dotenv()
EMAIL = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# ---------- DB ----------
def get_db():
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
        conn = get_db()
        cur = conn.cursor()

        cur.executescript("""
       CREATE TABLE IF NOT EXISTS producto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL,
        precio REAL NOT NULL,
        imagen TEXT NOT NULL,
        costo REAL NOT NULL,
        categoria TEXT NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            mesa INTEGER NOT NULL,
            email TEXT NOT NULL,
            fecha TEXT NOT NULL,
            estado TEXT NOT NULL,
            total REAL NOT NULL,
            factura TEXT
        );

        CREATE TABLE IF NOT EXISTS pedido_detalle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            FOREIGN KEY (pedido_id) REFERENCES pedido(id),
            FOREIGN KEY (producto_id) REFERENCES producto(id)
        );
        """)
        conn.commit()
        conn.close()

def insertar_productos():
        conn = get_db()
        cur = conn.cursor()

        productos = [
("La Bandera Dominicana", 550, "../static/img/Labadera.jpg", 165, "plato", 20),
("Mofongo", 480, "../static/img/Mofongo.jpg", 144, "plato", 15),
("Mangú con los 3 Golpes", 450, "../static/img/Los3golpe.jpg", 135, "plato", 25),
("Frito con Salami", 300, "../static/img/Fritosconsalami.jpg", 90, "plato", 30),
("Sancocho", 600, "../static/img/Sancocho.jpg", 180, "plato", 10),
("Locrio de Pollo", 500, "../static/img/Locriodepollo.webp", 150, "plato", 20),
("Locrio de Chuleta y Longaniza", 520, "../static/img/Locriodechuletayonganiza.jpg", 156, "plato", 20),

("Morir Soñando", 220, "../static/img/Morirsoñando.jpg", 66, "bebida", 40),
("Jugo de Chinola", 150, "../static/img/Jugodechinola.webp", 45, "bebida", 40),
("Jugo de Tamarindo", 160, "../static/img/JugoTamarido.png", 48, "bebida", 40),
("Pera Piña", 190, "../static/img/Perapiña.jpg", 57, "bebida", 30),
("Jugo de Limón", 140, "../static/img/Jugodelimón.jpeg", 42, "bebida", 40),
("Sangría", 250, "../static/img/Sangría.jpg", 75, "bebida", 20),

("Chacá", 200, "../static/img/Chacá.jpeg", 60, "postre", 25),
("Arroz con Leche", 180, "../static/img/Arrozconleche.jpg", 54, "postre", 25)
]
        for p in productos:
            cur.execute("""
                INSERT OR IGNORE INTO producto (nombre, precio, imagen, costo, categoria, stock)
                VALUES (?, ?, ?, ?, ?, ?)
            """, p)

        conn.commit()
        conn.close()

init_db()
insertar_productos()

    # ---------- ROUTES ----------
@app.route("/")
def index():
        conn = get_db()
        productos = conn.execute("""
            SELECT pr.nombre, pr.imagen, SUM(pd.cantidad) AS total
            FROM pedido_detalle pd
            JOIN producto pr ON pr.id = pd.producto_id
            GROUP BY pr.id
            ORDER BY total DESC
            LIMIT 3
        """).fetchall()
        conn.close()
        return render_template("index.html", productos=productos)

@app.route("/menu")
def menu():
        conn = get_db()
        productos = conn.execute("SELECT * FROM producto").fetchall()
        conn.close()
        return render_template("menu.html", productos=productos)

    #ADMIN: SOLO PEDIDOS ACTIVOS, ORDENADOS
@app.route("/admin")
def admin():
    conn = get_db()

    pedidos = conn.execute("""
        SELECT *
        FROM pedido
        WHERE estado NOT IN ('finalizado','Enviado')
        ORDER BY fecha ASC
    """).fetchall()

    data = []

    for p in pedidos:
        detalles = conn.execute("""
            SELECT pr.nombre, pd.cantidad
            FROM pedido_detalle pd
            JOIN producto pr ON pr.id = pd.producto_id
            WHERE pd.pedido_id = ?
        """, (p["id"],)).fetchall()

        data.append({"info": p, "detalles": detalles})

    # PRODUCTOS PARA EL CHEF
    productos = conn.execute(
        "SELECT id, nombre, stock FROM producto"
    ).fetchall()

    conn.close()

    return render_template("admin.html", pedidos=data, productos=productos)
# -------- CONTROL DE STOCK (CHEF) --------

@app.route("/stock_sumar", methods=["POST"])
def stock_sumar():
    data = request.json
    conn = get_db()

    conn.execute("""
        UPDATE producto
        SET stock = stock + ?
        WHERE id = ?
    """, (data["cantidad"], data["id"]))

    conn.commit()
    conn.close()

    return jsonify(success=True)


@app.route("/stock_agotado", methods=["POST"])
def stock_agotado():
    data = request.json
    conn = get_db()

    conn.execute("""
        UPDATE producto
        SET stock = 0
        WHERE id = ?
    """, (data["id"],))

    conn.commit()
    conn.close()

    return jsonify(success=True)
    # ---------- CREAR PEDIDO ----------
@app.route("/crear_pedido", methods=["POST"])
def crear_pedido():
        data = request.json
        print(data)

        if not data.get("email"):
            return jsonify(success=False, error="Email requerido")

        conn = get_db()
        cur = conn.cursor()

        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            INSERT INTO pedido (nombre, mesa, email, fecha, estado, total)
            VALUES (?, ?, ?, ?, 'pendiente', ?)
            """, (
                data.get("nombre"),
                data.get("mesa"),
                data.get("email"),
                fecha,
                data.get("total")
            ))

        pedido_id = cur.lastrowid

        for item in data["productos"]:

            producto = conn.execute(
            "SELECT id, stock FROM producto WHERE nombre = ?",
            (item["nombre"],)
             ).fetchone()

            if producto["stock"] < item["cantidad"]:
                return jsonify(success=False, error=f"No hay suficiente stock de {item['nombre']}")

            pid = producto["id"]

            cur.execute("""
             INSERT INTO pedido_detalle (pedido_id, producto_id, cantidad)
             VALUES (?, ?, ?)
            """, (pedido_id, pid, item["cantidad"]))
    
    

    # RESTAR STOCK
            conn.execute("""
             UPDATE producto
             SET stock = stock - ?
             WHERE id = ?
             """, (item["cantidad"], pid))

        conn.commit()
        conn.close()

        return jsonify(success=True)

    # CAMBIAR ESTADO (BOTONES ADMIN)
@app.route("/cambiar_estado", methods=["POST"])
def cambiar_estado():
        data = request.json
        conn = get_db()

        conn.execute("""
            UPDATE pedido
            SET estado = ?
            WHERE id = ?
        """, (data["estado"], data["id"]))

        conn.commit()
        conn.close()
        return jsonify(success=True)
    #--------Factura-------------
@app.route("/factura")
def factura():

        enviado = request.args.get("ok")

        conn = get_db()

        pedidos = conn.execute("""
            SELECT *
            FROM pedido
            WHERE estado = 'finalizado'
            ORDER BY fecha ASC
        """).fetchall()
        
        data = []
        
        for p in pedidos:
            detalles = conn.execute("""
                SELECT pr.nombre, pd.cantidad
                FROM pedido_detalle pd
                JOIN producto pr ON pr.id = pd.producto_id
                WHERE pd.pedido_id = ?
            """, (p["id"],)).fetchall()

            data.append({"info": p, "detalles": detalles})
            
        conn.close()

        return render_template("factura.html", pedidos=data, enviado=enviado)
    #---email---
def enviar_correo_factura(destino, estado, archivo):
        
        if not EMAIL or not EMAIL_PASSWORD:
            raise Exception("Debes configurar EMAIL_USER y EMAIL_PASS")
        
        if "@" not in destino or "." not in destino:
            print("Email inválido")
            return
        try:

            msg = EmailMessage()

            msg["Subject"] = "Factura - Restaurante El Pilón"
            msg["From"] = EMAIL
            msg["To"] = destino

            msg.set_content(f"""
    Hola,

    Gracias por visitar Restaurante El Pilón.

    Tu pedido ha sido completado y procesado correctamente.

    Estado del pedido: {estado}

    Adjunto encontrarás la factura correspondiente a tu pedido.

    Si tienes alguna pregunta o necesitas asistencia,
    no dudes en responder a este correo.

    Saludos cordiales,

    Equipo de Restaurante El Pilón
    """)

            with open(archivo, "rb") as f:
                ext = os.path.splitext(archivo)[1].replace(".", "")
                
                if ext in ["jpg", "jpeg", "png"]:
                    maintype = "image"
                else:
                    maintype = "application"

                msg.add_attachment(
                    f.read(),
                    maintype=maintype,
                    subtype=ext,
                    filename=os.path.basename(archivo)
                )

            with smtplib.SMTP_SSL("smtp.gmail.com",465) as smtp:
                smtp.login(EMAIL, EMAIL_PASSWORD)
                smtp.send_message(msg)


        except Exception as e:
            print("Error enviando correo:", str(e))
            
        print(f"Correo enviado correctamente a {destino}")
            
            
    #-----Envia factura--------
@app.route("/enviar_factura/<int:id>", methods=["POST"])
def enviar_factura(id):

        conn = get_db()

        pedido = conn.execute(
            "SELECT * FROM pedido WHERE id = ?",
            (id,)
        ).fetchone()

        archivo = request.files.get("archivo")
        
        if not archivo or archivo.filename == "":
            return jsonify({"success": False, "msg": "Debes subir una factura"})
        
        if pedido is None or pedido["estado"] == "Enviado":
            return redirect("/factura")
        
        if archivo and archivo.filename != "":

            fecha = datetime.now().strftime("%Y-%m-%d")

            nombre = pedido["nombre"].replace(" ", "_")
            nombre_archivo = f"{nombre}_{fecha}_{archivo.filename}"

            ext = os.path.splitext(archivo.filename)[1].lower()

            permitidos = [".pdf", ".png", ".jpg", ".jpeg", ".xlsx"]

            if ext not in permitidos:
                return jsonify({"success": False, "msg": "Solo se permiten PDF, imágenes o Excel"})

            os.makedirs("static/facturas", exist_ok=True)

            ruta = os.path.join("static/facturas", secure_filename(nombre_archivo))

            archivo.save(ruta)

            thread = threading.Thread(
                target=enviar_correo_factura,
                args=(pedido["email"], "Enviado", ruta)
            )

            thread.start()

            #   CAMBIAR ESTADO A ENVIADO
            conn.execute("""
                UPDATE pedido
                SET estado = 'Enviado', factura = ?
                WHERE id = ?
                """, (ruta, id))

            conn.commit()

        conn.close()

        return redirect("/factura?ok=1")
    #----------------------------------------
    #----------------------------------------




#Solo no da;e lo que esta bien echo pls
    # --- RUTA: PANEL DE LAS PUTAS DE MERCADEO ---

def costo_defecto(precio):
        return round(precio * 0.30, 2)

def calc_margen(row):
        precio = float(row["precio"])
        costo = float(row["costo"]) if ("costo" in row.keys() and row["costo"] not in (None, 0, "")) else costo_defecto(precio)
        margen_unit = round(precio - costo, 2)
        margen_pct = round((margen_unit / precio) * 100, 2) if precio else 0
        return precio, costo, margen_unit, margen_pct
        

@app.route("/panel")
def panel_marketing():
        conn = get_db()

        # 1) Productos con margen (INTACTO)
        productos = conn.execute("SELECT id, nombre, precio, costo, categoria, stock FROM producto").fetchall()
        productos_list = []
        for p in productos:
            precio, costo, margen_unit, margen_pct = calc_margen(p)
            productos_list.append({
                "id": p["id"],
                "nombre": p["nombre"],
                "categoria": p["categoria"] if "categoria" in p.keys() else "general",
                "precio": precio,
                "costo": costo,
                "margen_unit": margen_unit,
                "margen_pct": margen_pct
            })

        # 2) Top ventas (cantidad vendida por producto) (INTACTO)
        top_ventas = conn.execute("""
            SELECT pr.id, pr.nombre, pr.precio, SUM(pd.cantidad) AS cantidad_vendida
            FROM pedido_detalle pd
            JOIN producto pr ON pr.id = pd.producto_id
            GROUP BY pr.id
            ORDER BY cantidad_vendida DESC
            LIMIT 10
        """).fetchall()

        ventas_list = []
        for v in top_ventas:
            precio, costo, margen_unit, margen_pct = calc_margen(v)
            cantidad = int(v["cantidad_vendida"] or 0)
            ingresos_prod = round(precio * cantidad, 2)
            ganancia_prod = round(margen_unit * cantidad, 2)
            ventas_list.append({
                "id": v["id"],
                "nombre": v["nombre"],
                "cantidad": cantidad,
                "precio": precio,
                "ingresos": ingresos_prod,
                "ganancia": ganancia_prod
            })

        # =========================================================
        # 3) MÉTRICAS REALES EN TIEMPO REAL (NUEVO)
        # =========================================================
        
        # Obtenemos el total de pedidos y la suma de dinero real de pedidos finalizados o enviados
        metricas_reales = conn.execute("""
            SELECT 
                COUNT(id) as total_pedidos, 
                SUM(total) as ingreso_total 
            FROM pedido 
            WHERE estado IN ('finalizado', 'Enviado')
        """).fetchone()

        total_pedidos = metricas_reales["total_pedidos"] or 0
        ingreso_mensual = metricas_reales["ingreso_total"] or 0

        # Calculamos el costo real cruzando los detalles de los pedidos con el costo de cada producto
        costos_reales = conn.execute("""
            SELECT SUM(pd.cantidad * pr.costo) as costo_total
            FROM pedido_detalle pd
            JOIN pedido p ON p.id = pd.pedido_id
            JOIN producto pr ON pr.id = pd.producto_id
            WHERE p.estado IN ('finalizado', 'Enviado')
        """).fetchone()

        costos_mensuales = costos_reales["costo_total"] or 0

        # Cálculos derivados basados en la realidad
        gasto_prom = round(ingreso_mensual / total_pedidos, 2) if total_pedidos > 0 else 0
        ganancia_mensual = round(ingreso_mensual - costos_mensuales, 2)
        margen_pct_total = round((ganancia_mensual / ingreso_mensual) * 100, 2) if ingreso_mensual > 0 else 0

        # Promedios diarios (asumiendo un mes de 30 días para la proyección de tu panel)
        dias_mes = 30
        clientes_dia = round(total_pedidos / dias_mes)
        ingreso_diario = round(ingreso_mensual / dias_mes, 2)

        # =========================================================
        # 4) Producto más rentable y más vendido (INTACTO)
        # =========================================================
        producto_mas_rentable = max(productos_list, key=lambda x: x["margen_unit"]) if productos_list else None
        producto_mas_vendido = max(ventas_list, key=lambda x: x["cantidad"]) if ventas_list else None

        conn.close()

        # Segmentacion estática (INTACTA)
        segmentacion = {
            "demografica": [
                {"edad":"18-25","porcentaje":"35%","descripcion":"Jóvenes que buscan comida rápida y salidas con amigos."},
                {"edad":"26-40","porcentaje":"30%","descripcion":"Adultos jóvenes, parejas y trabajadores."},
                {"edad":"41-60","porcentaje":"25%","descripcion":"Familias y reuniones sociales."},
                {"edad":"60+","porcentaje":"10%","descripcion":"Adultos mayores, visitas ocasionales al malecón/acuario."}
            ],
            "economica": [
                {"nivel":"Bajo","porcentaje":"25%","gasto":"RD$200 - RD$350"},
                {"nivel":"Medio","porcentaje":"50%","gasto":"RD$400 - RD$700"},
                {"nivel":"Medio-alto","porcentaje":"25%","gasto":"RD$800 - RD$1,200"}
            ],
            "conductual": [
                {"tipo":"Visitantes recreativos","porcentaje":"35%","descripcion":"Personas caminando por el malecón buscando comida rápida."},
                {"tipo":"Familias acuario","porcentaje":"25%","descripcion":"Buscan comodidad y comida tradicional."},
                {"tipo":"Jóvenes nocturnos","porcentaje":"25%","descripcion":"Platos rápidos: hamburguesas, pizza, etc."},
                {"tipo":"Turistas","porcentaje":"15%","descripcion":"Buscan comida típica y experiencia local."}
            ]
        }

        return render_template("panel.html",
                            productos=productos_list,
                            ventas=ventas_list,
                            clientes_dia=clientes_dia,
                            gasto_prom=gasto_prom,
                            dias_mes=dias_mes,
                            costos_mensuales=costos_mensuales,
                            ingreso_diario=ingreso_diario,
                            ingreso_mensual=ingreso_mensual,
                            ganancia_mensual=ganancia_mensual,
                            margen_pct_total=margen_pct_total,
                            producto_mas_rentable=producto_mas_rentable,
                            producto_mas_vendido=producto_mas_vendido,
                            segmentacion=segmentacion)

if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000,debug=True)