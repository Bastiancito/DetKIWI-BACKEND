from app.extensions import db
# Ajusta la importación de modelos según la estructura de tu proyecto
from app.models import User, Paralelo

# 1. Los datos que deseas ingresar
nuevos_usuarios_data = [
  { "username": "felipe.dumont", "email": "felipe.dumont@usm.cl", "password": "felipe123", "rol_id": 2, "paralelo_ids": ["INF129_1L", "INF129_7L"] },
  { "username": "gustavo.ulloa", "email": "gustavo.ulloa@usm.cl", "password": "gustavo123", "rol_id": 2, "paralelo_ids": ["INF129_2L", "INF129_5L", "INF129_11L", "INF129_22L", "IWI131_6L"] },
  { "username": "paulina.gonzalez", "email": "paulina.gonzalez@usm.cl", "password": "paulina123", "rol_id": 2, "paralelo_ids": ["INF129_3L", "INF129_17L", "EIN413-B_300", "EIN413-B_301"] },
  { "username": "alvaro.salinas", "email": "alvaro.salinas@usm.cl", "password": "alvaro123", "rol_id": 2, "paralelo_ids": ["INF129_4L", "INF129_16L"] },
  { "username": "juan.zamora", "email": "juan.zamora@usm.cl", "password": "juan123", "rol_id": 2, "paralelo_ids": ["INF129_6L"] },
  { "username": "pablo.cruz", "email": "pablo.cruz@usm.cl", "password": "pablo123", "rol_id": 2, "paralelo_ids": ["INF129_8L", "INF129_18L"] },
  { "username": "diego.vicencio", "email": "diego.vicencio@usm.cl", "password": "diego123", "rol_id": 2, "paralelo_ids": ["INF129_9L"] },
  { "username": "jean-pierre.villacura", "email": "jean-pierre.villacura@usm.cl", "password": "jean-pierre123", "rol_id": 2, "paralelo_ids": ["INF129_10L"] },
  { "username": "andrea.freire", "email": "andrea.freire@usm.cl", "password": "andrea123", "rol_id": 2, "paralelo_ids": ["INF129_12L", "INF129_14L"] },
  { "username": "andres.navarro", "email": "andres.navarro@usm.cl", "password": "andres123", "rol_id": 2, "paralelo_ids": ["INF129_13L", "INF129_15L", "INF129_20L"] },
  { "username": "miguel.guevara", "email": "miguel.guevara@usm.cl", "password": "miguel123", "rol_id": 2, "paralelo_ids": ["INF129_19L", "INF129_21L"] },
  { "username": "juan.jerez", "email": "juan.jerez@usm.cl", "password": "juan123", "rol_id": 2, "paralelo_ids": ["INF129_100L", "IWI131_101L", "IWI131_102L"] },
  { "username": "ricardo.von", "email": "ricardo.von@usm.cl", "password": "ricardo123", "rol_id": 2, "paralelo_ids": ["INF129_101L", "IWI131_100L"] },
  { "username": "cristobal.loyola", "email": "cristobal.loyola@usm.cl", "password": "cristobal123", "rol_id": 2, "paralelo_ids": ["INF129_200L", "INF129_203L", "INF129_205L", "INF129_208L", "INF129_211L", "IWI131_203L"] },
  { "username": "viktor.tapia", "email": "viktor.tapia@usm.cl", "password": "viktor123", "rol_id": 2, "paralelo_ids": ["INF129_201L", "INF129_202L", "INF129_214L", "INF129_217L"] },
  { "username": "rodrigo.caviedes", "email": "rodrigo.caviedes@usm.cl", "password": "rodrigo123", "rol_id": 2, "paralelo_ids": ["INF129_204L", "INF129_209L", "IWI131_202L"] },
  { "username": "luis.ramirez", "email": "luis.ramirez@usm.cl", "password": "luis123", "rol_id": 2, "paralelo_ids": ["INF129_206L", "INF129_210L", "INF129_213L", "IWI131_200L", "IWI131_204L"] },
  { "username": "pedro.toledo", "email": "pedro.toledo@usm.cl", "password": "pedro123", "rol_id": 2, "paralelo_ids": ["INF129_207L", "IWI131_201L"] },
  { "username": "anibal.silva", "email": "anibal.silva@usm.cl", "password": "anibal123", "rol_id": 2, "paralelo_ids": ["INF129_212L", "INF129_215L", "INF129_216L", "INF129_218L"] },
  { "username": "alejandro.veloz", "email": "alejandro.veloz@usm.cl", "password": "alejandro123", "rol_id": 2, "paralelo_ids": ["IWI131_1L", "IWI131_5L"] },
  { "username": "claudio.jara", "email": "claudio.jara@usm.cl", "password": "claudio123", "rol_id": 2, "paralelo_ids": ["IWI131_2L", "IWI131_3L"] },
  { "username": "andrea.vasquez", "email": "andrea.vasquez@usm.cl", "password": "andrea123", "rol_id": 2, "paralelo_ids": ["IWI131_4L"] },
  { "username": "pamela.gatica", "email": "pamela.gatica@usm.cl", "password": "pamela123", "rol_id": 2, "paralelo_ids": ["EIN413-B_302"] },
  { "username": "cristian.lara", "email": "cristian.lara@usm.cl", "password": "cristian123", "rol_id": 2, "paralelo_ids": ["EIN413-B_701"] },
  { "username": "juan.gonzalez", "email": "juan.gonzalez@usm.cl", "password": "juan123", "rol_id": 2, "paralelo_ids": ["EIN413-B_702"] },
  { "username": "ana.rojas", "email": "ana.rojas@usm.cl", "password": "ana123", "rol_id": 2, "paralelo_ids": ["ELI109_A_300", "ELI109_A_301"] },
  { "username": "claudio.velquen", "email": "claudio.velquen@usm.cl", "password": "claudio123", "rol_id": 2, "paralelo_ids": ["ELI109_A_701"] }
]

# 2. Usuarios obtenidos de Postman que ya existen
usuarios_existentes_postman = [
    { "email": "bastiancamus77@gmail.com", "username": "bastian" },
    { "email": "rodrigo.caviedes@usm.cl", "username": "rodrigo.caviedes" },
    { "email": "pablo.cruz@usm.cl", "username": "pablo.cruz" },
    { "email": "felipe.dumont@usm.cl", "username": "felipe.dumont" },
    { "email": "andrea.freire@usm.cl", "username": "andrea.freire" },
    { "email": "paulina.gonzalezp@usm.cl", "username": "paulina.gonzalezp" },
    { "email": "miguel.guevara@usm.cl", "username": "miguel.guevara" },
    { "email": "claudio.jarac@usm.cl", "username": "claudio.jarac" },
    { "email": "juan.jerez@usm.cl", "username": "juan.jerez" },
    { "email": "cristobal.loyolam@usm.cl", "username": "cristobal.loyolam" },
    { "email": "andres.navarrog@usm.cl", "username": "andres.navarrog" },
    { "email": "luis.ramirezd@usm.cl", "username": "luis.ramirezd" },
    { "email": "alvaro.salinas@usm.cl", "username": "alvaro.salinas" },
    { "email": "anibal.silvao@usm.cl", "username": "anibal.silvao" },
    { "email": "viktor.tapia@usm.cl", "username": "viktor.tapia" },
    { "email": "pedro.toledo@usm.cl", "username": "pedro.toledo" },
    { "email": "gustavo.ulloa@usm.cl", "username": "gustavo.ulloa" },
    { "email": "alejandro.veloz@usm.cl", "username": "alejandro.veloz" },
    { "email": "diego.vicencio@alumnos.usm.cl", "username": "diego.vicencio" },
    { "email": "jean-pierre.rojas@sansano.usm.cl", "username": "jean-pierre.rojas" },
    { "email": "ricardo.vonkretschma@usm.cl", "username": "ricardo.vonkretschma" },
    { "email": "juan.zamora@usm.cl", "username": "juan.zamora" }
]

def seed_usuarios():
    # Convertimos los existentes en Sets para una búsqueda mucho más rápida
    emails_existentes = {u['email'] for u in usuarios_existentes_postman}
    usernames_existentes = {u['username'] for u in usuarios_existentes_postman}

    usuarios_creados = 0
    usuarios_saltados = 0

    for user_data in nuevos_usuarios_data:
        # 1. Filtramos contra la lista de Postman
        if user_data['username'] in usernames_existentes or user_data['email'] in emails_existentes:
            print(f"⏭️ Saltando: {user_data['username']} (Ya está en la lista de Postman)")
            usuarios_saltados += 1
            continue
        
        # 2. Filtramos contra la BD directamente por seguridad adicional
        db_user = User.query.filter((User.username == user_data['username']) | (User.email == user_data['email'])).first()
        if db_user:
            print(f"⏭️ Saltando: {user_data['username']} (Ya existe en la Base de Datos)")
            usuarios_saltados += 1
            continue

        # 3. Instanciar nuevo usuario
        nuevo_usuario = User(
            username=user_data['username'],
            email=user_data['email'],
            rol_id=user_data['rol_id']
        )
        nuevo_usuario.set_password(user_data['password'])

        # 4. Procesar y enlazar los paralelos (usando las siglas)
        for sigla in user_data['paralelo_ids']:
            # Buscamos si la sigla ya existe en la tabla Paralelo
            paralelo = Paralelo.query.filter_by(sigla_paralelo=sigla).first()
            
            # Si no existe, lo creamos e insertamos en la BD en el momento
            if not paralelo:
                paralelo = Paralelo(sigla_paralelo=sigla)
                db.session.add(paralelo)
                # Flush permite obtener un ID sin hacer commit, útil si hay varios usuarios con el mismo paralelo nuevo
                db.session.flush() 

            # Agregamos la relación al nuevo usuario
            nuevo_usuario.paralelos.append(paralelo)

        # 5. Agregar el usuario completo a la sesión
        db.session.add(nuevo_usuario)
        usuarios_creados += 1
        print(f"✅ Creado: {user_data['username']} con {len(user_data['paralelo_ids'])} paralelos.")

    # Guardamos los cambios en la base de datos
    db.session.commit()
    print("-" * 30)
    print(f"Resumen: {usuarios_creados} usuarios creados, {usuarios_saltados} usuarios omitidos.")

# Si lo llamas desde un contexto Flask de shell o comando CLI, quita los comentarios de abajo:
if __name__ == '__main__':
     from app import create_app
     app = create_app()
     with app.app_context():
            seed_usuarios()