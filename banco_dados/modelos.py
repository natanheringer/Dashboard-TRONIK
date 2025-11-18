from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Lixeira(db.Model):
    __tablename__ = "lixeiras"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    localizacao = db.Column(db.String(255), nullable=False)
    nivel = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="OK")

    def atualizar_status(self):
        if self.nivel >= 90:
            self.status = "CRITICO"
        elif self.nivel >= 80:
            self.status = "ALERTA"
        else:
            self.status = "OK"

class Sensor(db.Model):
    __tablename__ = "sensores"
    id = db.Column(db.Integer, primary_key=True)
    identificador = db.Column(db.String(100), unique=True, nullable=False)
    lixeira_id = db.Column(db.Integer, db.ForeignKey("lixeiras.id"), nullable=False)
    lixeira = db.relationship("Lixeira", backref="sensores")
