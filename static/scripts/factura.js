const params = new URLSearchParams(window.location.search)

if(params.get("ok") === "1"){

    const modal = document.getElementById("modal")

    modal.style.display = "flex"

    setTimeout(()=>{
        modal.style.display = "none"
    },2000)

}

// recargar la pagina cada 5 segundos
setInterval(() => {
    window.location.reload();
}, 25000);