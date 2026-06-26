function cargarHabitaciones() {
    fetch('/habitaciones')
        .then(res => res.json())
        .then(data => {
            document.getElementById("resultado").innerHTML =
                JSON.stringify(data, null, 2);
        });
}
