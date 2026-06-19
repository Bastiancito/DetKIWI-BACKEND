El primer usuario sanciona el caso(http://localhost:5000/api/casos/SancionarCaso/84) y envia este payload:

{
    "sancion": true,
    "reason": {
        "518": {
            "motivo": "Se uso contenido no entregado en clases",
            "descripcion": "jaja"
        }
    }
}


y obtiene este response:

{
  "caso": {
    "caso_id": 845,
    "caso_metadata": null,
    "closed": false,
    "comentarios_profes": null,
    "decisiones_profes": {
      "518": true
    },
    "estudiantes": [
      {
        "apellido": "",
        "estudiante_id": 1575,
        "nombre": "Aaron David Irribarra Ilabaca",
        "paralelo": "INF129_5L"
      },
      {
        "apellido": "",
        "estudiante_id": 1576,
        "nombre": "Martin Angel Olivares Ahumada",
        "paralelo": "INF129_17L"
      }
    ],
    "evaluacion_id": 7,
    "in_process": true,
    "lineas": 0,
    "motivo_sancion": {
      "518": {
        "descripcion": "jaja",
        "motivo": "Se uso contenido no entregado en clases"
      }
    },
    "paralelos": [
      {
        "paralelo_id": 1411,
        "sede_id": null,
        "sede_nombre": null,
        "sigla_paralelo": "INF129_5L"
      },
      {
        "paralelo_id": 1416,
        "sede_id": null,
        "sede_nombre": null,
        "sigla_paralelo": "INF129_17L"
      }
    ],
    "reporte_id": 42,
    "sancion": null,
    "similitud": 60.0,
    "url_moss": "http://moss.stanford.edu/results/1/2291555445144/",
    "usuarios_asignados": [
      {
        "email": "gustavo.ulloau@usm.cl",
        "user_id": 517,
        "username": "gustavo.ulloa"
      },
      {
        "email": "paulina.gonzalezp@usm.cl",
        "user_id": 518,
        "username": "paulina.gonzalez"
      }
    ]
  },
  "msg": "Voto registrado"
}


Sin embargo, el segundo usuario responsable del caso hace por alguna razon uso del endpoint: http://localhost:5000/api/casos/CambiarOpinion/845 ---> FRONTEND LO DESVIA A ESTE ENDPOINT 

envia el payload:

{
    "sancion": true,
    "reason": {
        "517": {
            "motivo": "Se detecto uso de inteligencia artificial",
            "descripcion": "JAJAJAJAJAJ"
        }
    }
}

y obtiene el response:

{
  "applied_vote": true,
  "caso": {
    "caso_id": 845,
    "caso_metadata": {
      "historial_cambios_opinion": [
        {
          "desde": null,
          "hacia": true,
          "motivo_anterior": null,
          "timestamp": "2026-06-18T23:54:39.477289",
          "user_id": 517
        }
      ]
    },
    "closed": true,
    "comentarios_profes": null,
    "decisiones_profes": {
      "517": true,
      "518": true
    },
    "estudiantes": [
      {
        "apellido": "",
        "estudiante_id": 1575,
        "nombre": "Aaron David Irribarra Ilabaca",
        "paralelo": "INF129_5L"
      },
      {
        "apellido": "",
        "estudiante_id": 1576,
        "nombre": "Martin Angel Olivares Ahumada",
        "paralelo": "INF129_17L"
      }
    ],
    "evaluacion_id": 7,
    "in_process": false,
    "lineas": 0,
    "motivo_sancion": {
      "517": {
        "descripcion": "JAJAJAJAJAJ",
        "motivo": "Se detecto uso de inteligencia artificial"
      },
      "518": {
        "descripcion": "jaja",
        "motivo": "Se uso contenido no entregado en clases"
      }
    },
    "paralelos": [
      {
        "paralelo_id": 1411,
        "sede_id": null,
        "sede_nombre": null,
        "sigla_paralelo": "INF129_5L"
      },
      {
        "paralelo_id": 1416,
        "sede_id": null,
        "sede_nombre": null,
        "sigla_paralelo": "INF129_17L"
      }
    ],
    "reporte_id": 42,
    "sancion": true,
    "similitud": 60.0,
    "url_moss": "http://moss.stanford.edu/results/1/2291555445144/",
    "usuarios_asignados": [
      {
        "email": "gustavo.ulloau@usm.cl",
        "user_id": 517,
        "username": "gustavo.ulloa"
      },
      {
        "email": "paulina.gonzalezp@usm.cl",
        "user_id": 518,
        "username": "paulina.gonzalez"
      }
    ]
  },
  "msg": "Opini\u00f3n cambiada"
}




