let cart = [];

/* ================= CARRITO ================= */
function toggleCart(){
    document.getElementById("cart").classList.toggle("open");
}

/* ================= AGREGAR ================= */
function addToCart(nombre, precio, imagen, stock){

    let item = cart.find(p => p.nombre === nombre);

    if(item){
        if(item.cantidad >= stock){
            alert("No hay más stock disponible");
            return;
        }
        item.cantidad++;
    }else{
        cart.push({
            nombre,
            precio,
            imagen,
            cantidad: 1,
            stock: stock
        });
    }

    renderCart();
}

/* ================= SUMAR ================= */
function increase(nombre){

    let item = cart.find(p => p.nombre === nombre);

    if(item){

        if(item.cantidad >= item.stock){
            alert("No hay más stock disponible");
            return;
        }

        item.cantidad++;
        renderCart();
    }
}

/* ================= RESTAR ================= */
function decrease(nombre){
    let item = cart.find(p => p.nombre === nombre);
    if(item){
        item.cantidad--;
        if(item.cantidad <= 0){
            cart = cart.filter(p => p.nombre !== nombre);
        }
        renderCart();
    }
}

/* ================= ELIMINAR ================= */
function removeItem(nombre){
    cart = cart.filter(p => p.nombre !== nombre);
    renderCart();
}

/* ================= RENDER ================= */
function renderCart(){
    let cont = document.getElementById("cartItems");
    let total = 0;
    let count = 0;

    cont.innerHTML = "";

    cart.forEach(p => {
    total += p.precio * p.cantidad;
    count += p.cantidad;

    cont.innerHTML += `
    <div class="cart-item">
        <div class="cart-img" style="background-image: url('${p.imagen}');"></div>
        <div style="flex:1">
            <strong>${p.nombre}</strong><br>
            RD$${p.precio} x ${p.cantidad}
            <div style="margin-top:6px">
                <button onclick="decrease('${p.nombre}')">➖</button>
                <button onclick="increase('${p.nombre}')">➕</button>
                <button onclick="removeItem('${p.nombre}')">❌</button>
            </div>
        </div>
    </div>`;
});

    document.getElementById("total").innerText = total;
    document.getElementById("cartCount").innerText = count;
}

/* ================= MODAL ================= */
function mostrarModal(icon, titulo, mensaje){
    document.getElementById("modalIcon").src = icon;
    document.getElementById("modalTitle").innerText = titulo;
    document.getElementById("modalMsg").innerText = mensaje;
    document.getElementById("modal").style.display = "flex";
}

function cerrarModal(){
    document.getElementById("modal").style.display = "none";
}

/* ================= ENVIAR ================= */
function enviarPedido(){

    const nombre = document.getElementById("nombre").value;
    const mesa = document.getElementById("mesa").value;
    const email = document.getElementById("email").value;

    if(!nombre || !mesa || !email){
        mostrarModal(
            "/static/img/error.png",
            "Datos incompletos",
            "Debes poner tu nombre, mesa y email"
        );
        return;
    }

    if(cart.length === 0){
        mostrarModal(
            "/static/img/error.png",
            "Carrito vacío",
            "Agrega productos antes de pedir"
        );
        return;
    }

    let total = parseFloat(document.getElementById("total").innerText);

    fetch("/crear_pedido",{
        method:"POST",
        headers:{
            "Content-Type":"application/json"
        },
        body:JSON.stringify({
            nombre:nombre,
            mesa:mesa,
            email:email,
            productos:cart,
            total:total
        })
    })
    .then(res => res.json())
    .then(data=>{
        if(data.success){
            mostrarModal(
                "/static/img/success.png",
                "Pedido enviado",
                "Tu pedido está en proceso 🍽️"
            );

            cart = [];
            renderCart();
            toggleCart();

            setTimeout(()=>{
               location.reload();
            },1500);
        }
    });
}

/* FILTRAR MENU */

function filtrarMenu(cat,btn){

let secciones=document.querySelectorAll(".categoria");
let botones=document.querySelectorAll(".nav-btn");

secciones.forEach(s=>{
s.style.display="none";
});

document.getElementById(cat).style.display="block";

botones.forEach(b=>{
b.classList.remove("active");
});

btn.classList.add("active");

}

/* mostrar platos al cargar */

window.onload=()=>{
filtrarMenu("platos",document.querySelector(".nav-btn"));
}