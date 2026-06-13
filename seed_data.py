#!/usr/bin/env python
"""Script para insertar datos iniciales en la base de datos"""

from app import create_app
from app.extensions import db
from app.models import Rol, User, Periodo, Evaluacion, Sede
from datetime import datetime, timedelta

def seed_database():
    app = create_app()
    
    with app.app_context():
        # Limpiar datos existentes (opcional)
        print("Iniciando seed de datos...")
        
        # 1. Crear Roles
        print("\n[*] Creando roles...")
        rol_coordinador = Rol.query.filter_by(nombre='Coordinador').first()
        if not rol_coordinador:
            rol_coordinador = Rol(nombre='Coordinador', descripcion='Coordinador del programa')
            db.session.add(rol_coordinador)
            print("  ✓ Rol 'Coordinador' creado")
        
        rol_profesor = Rol.query.filter_by(nombre='Profesor').first()
        if not rol_profesor:
            rol_profesor = Rol(nombre='Profesor', descripcion='Profesor del programa')
            db.session.add(rol_profesor)
            print("  ✓ Rol 'Profesor' creado")
        
        db.session.commit()
        
        # 1.5. Crear Sedes
        print("\n[*] Creando sedes...")
        sedes_data = ['Concepción', 'Casa Central', 'San Joaquín']
        for sede_nombre in sedes_data:
            sede = Sede.query.filter_by(nombre=sede_nombre).first()
            if not sede:
                sede = Sede(nombre=sede_nombre)
                db.session.add(sede)
                print(f"  ✓ Sede '{sede_nombre}' creada")
            else:
                print(f"  ! Sede '{sede_nombre}' ya existe")
        
        db.session.commit()
        
        # 2. Crear Usuario
        print("\n[*] Creando usuario...")
        user = User.query.filter_by(email='bastiancamus77@gmail.com').first()
        if not user:
            user = User(
                username='bastian',
                email='bastiancamus77@gmail.com',
                rol_id=rol_coordinador.rol_id
            )
            user.set_password('pruebas123')
            db.session.add(user)
            print("  ✓ Usuario 'bastian' (bastiancamus77@gmail.com) creado")
        else:
            print("  ! Usuario ya existe, actualizando contraseña...")
            user.set_password('pruebas123')
        
        db.session.commit()
        
        # 3. Crear Período
        print("\n[*] Creando período...")
        periodo = Periodo.query.filter_by(nombre='2026-1').first()
        if not periodo:
            periodo = Periodo(
                nombre='2026-1',
                anio=2026,
                semestre=1,
                activo=True
            )
            db.session.add(periodo)
            print("  ✓ Período '2026-1' creado")
        else:
            print("  ! Período ya existe")
        
        db.session.commit()
        
        # 4. Crear Evaluación
        print("\n[*] Creando evaluación...")
        evaluacion = Evaluacion.query.filter_by(nombre='Evaluación Inicial').first()
        if not evaluacion:
            evaluacion = Evaluacion(
                nombre='Evaluación Inicial',
                descripcion='Primera evaluación del período',
                periodo_id=periodo.periodo_id,
                fecha_entrega=datetime.utcnow() + timedelta(days=30),
                activo=True
            )
            db.session.add(evaluacion)
            print("  ✓ Evaluación 'Evaluación Inicial' creada")
        else:
            print("  ! Evaluación ya existe")
        
        db.session.commit()
        
        print("\n✅ Seed completado exitosamente!\n")
        print("Datos creados:")
        print(f"  - Sedes: Concepción, Casa Central, San Joaquín")
        print(f"  - Usuario: bastiancamus77@gmail.com / pruebas123")
        print(f"  - Rol Coordinador: {rol_coordinador.rol_id}")
        print(f"  - Rol Profesor: {rol_profesor.rol_id}")
        print(f"  - Período: {periodo.nombre}")
        print(f"  - Evaluación: {evaluacion.nombre}")

if __name__ == '__main__':
    seed_database()
