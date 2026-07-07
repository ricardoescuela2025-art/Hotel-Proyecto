use ReservasHotel

SELECT * FROM Usuarios
SELECT * FROM Reportes

CREATE TABLE Usuarios (
    id INT IDENTITY(1,1) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(100) UNIQUE NOT NULL,
    contraseña VARCHAR(200) NOT NULL,
    telefono VARCHAR(20),
    tipo VARCHAR(20) NOT NULL   -- admin, recepcionista, usuario
);

CREATE TABLE Habitaciones (
    id INT IDENTITY(1,1) PRIMARY KEY,
    numero VARCHAR(10) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    tipo VARCHAR(50) NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    estado VARCHAR(20) NOT NULL,
    descripcion VARCHAR(MAX),
    estrellas INT,
    imagen VARCHAR(300)
);


CREATE TABLE Reservas (
    id INT IDENTITY(1,1) PRIMARY KEY,
    usuario_id INT NOT NULL,
    habitacion_id INT NOT NULL,
    fecha_entrada DATE NOT NULL,
    fecha_salida DATE NOT NULL,
    estado VARCHAR(20) NOT NULL, -- activa, finalizada, pendiente
    FOREIGN KEY (usuario_id) REFERENCES Usuarios(id),
    FOREIGN KEY (habitacion_id) REFERENCES Habitaciones(id)
);


CREATE TABLE Reportes (
    id INT IDENTITY(1,1) PRIMARY KEY,
    room_number VARCHAR(20) NOT NULL,      -- n�mero de habitaci�n
    incident_type VARCHAR(100) NOT NULL,   -- tipo de incidente
    description VARCHAR(MAX) NOT NULL,     -- descripci�n del reporte
    created_at DATETIME NOT NULL DEFAULT GETDATE()  -- fecha creaci�n
);

