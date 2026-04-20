#%% Librerías
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

#%% Configuración de la página
st.set_page_config(page_title="Quiniela Mundial 2026", page_icon="🏆", layout="wide")

st.title("🏆 Quiniela Mundial 2026")

#%% Parámetros de conexión a datos
# IMPORTANTE: Reemplaza estos textos por tus links reales
URLS = {
    "partidos_reales": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZbq9qrwyKvdkLwRyH3L_lS7lY-tQyiipROQy_vVDl5T4Rvy1coj1O4Y5SmaTJxdgRXhNNhc5j4-IJ/pub?gid=0&single=true&output=csv",
    "premios_reales": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZbq9qrwyKvdkLwRyH3L_lS7lY-tQyiipROQy_vVDl5T4Rvy1coj1O4Y5SmaTJxdgRXhNNhc5j4-IJ/pub?gid=1387163280&single=true&output=csv",
    "pronosticos_partidos": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZbq9qrwyKvdkLwRyH3L_lS7lY-tQyiipROQy_vVDl5T4Rvy1coj1O4Y5SmaTJxdgRXhNNhc5j4-IJ/pub?gid=1543421484&single=true&output=csv",
    "pronosticos_premios": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZbq9qrwyKvdkLwRyH3L_lS7lY-tQyiipROQy_vVDl5T4Rvy1coj1O4Y5SmaTJxdgRXhNNhc5j4-IJ/pub?gid=309429808&single=true&output=csv",
    "mapeo_jugadores": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQZbq9qrwyKvdkLwRyH3L_lS7lY-tQyiipROQy_vVDl5T4Rvy1coj1O4Y5SmaTJxdgRXhNNhc5j4-IJ/pub?gid=102280143&single=true&output=csv" 
}

#%% Funciones
@st.cache_data(ttl=10, show_spinner=False) # Refresca los datos cada 10 segundos
def cargar_datos(url):
    try:
        # Pandas lee el CSV público directamente desde la web en milisegundos
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Error conectando a la URL: {e}")
        return pd.DataFrame()

# --- MOTOR DE PUNTUACIÓN ---

def calcular_posiciones(df_partidos, df_premios, df_pronos_part, df_pronos_premios, df_jugadores):
    # ---------------------------------------------------------
    # 1. EVALUACIÓN DE PARTIDOS (3 pts pleno, 1 pt ganador)
    # ---------------------------------------------------------
    
    # Unimos los pronósticos con los resultados reales usando el 'id_partido'
    df_p = pd.merge(df_pronos_part, df_partidos, on='id_partido', how='left')
    df_p = pd.merge(df_p, df_jugadores, on='id_jugador', how='left')
    
    # Filtramos SOLO los partidos que ya se jugaron (donde tú ya anotaste goles reales)
    df_p = df_p.dropna(subset=['goles_local_real', 'goles_visitante_real'])
    
    # Función para determinar la tendencia (Local, Visitante, o Empate)
    def obtener_tendencia(goles_local, goles_visitante):
        if goles_local > goles_visitante: return 'L'
        elif goles_local < goles_visitante: return 'V'
        return 'E'

    # Calculamos los puntos si hay partidos jugados
    if not df_p.empty:
        # Tendencias reales vs Pronosticadas
        df_p['tendencia_real'] = df_p.apply(lambda x: obtener_tendencia(x['goles_local_real'], x['goles_visitante_real']), axis=1)
        df_p['tendencia_prono'] = df_p.apply(lambda x: obtener_tendencia(x['goles_local_pronostico'], x['goles_visitante_pronostico']), axis=1)

        # Reglas de Puntuación
        def asignar_puntos_partido(row):
            # Acierto Pleno (3 puntos)
            if (row['goles_local_real'] == row['goles_local_pronostico']) and (row['goles_visitante_real'] == row['goles_visitante_pronostico']):
                return 3
            # Acierto de Tendencia (1 punto)
            elif row['tendencia_real'] == row['tendencia_prono']:
                return 1
            # Fallo total (0 puntos)
            return 0
        
        df_p['puntos_partidos'] = df_p.apply(asignar_puntos_partido, axis=1)
        # Sumamos los puntos por jugador
        pts_partidos = df_p.groupby(['id_jugador'])['puntos_partidos'].sum().reset_index()
    else:
        # Si aún no empieza el mundial, todos tienen 0
        pts_partidos = pd.DataFrame({'id_jugador': df_jugadores['id_jugador'], 'puntos_partidos': 0})

    # ---------------------------------------------------------
    # 2. EVALUACIÓN DE PREMIOS Y CLASIFICADOS
    # ---------------------------------------------------------
    
    # Diccionario maestro de tus reglas de puntuación por fase
    puntos_por_categoria = {
        '16vos': 1,
        '8vos': 1,
        '4tos': 5,
        'Semis': 4,
        'Final': 3,
        'Campeón': 5,
        'Tercer lugar': 3,
        'Goleador': 6
    }

    # Unimos los pronósticos con el catálogo de premios
    df_pr = pd.merge(df_pronos_premios, df_premios, on='id_premio', how='left')

    list_df_pr = []
    categorias = df_pr['categoria'].unique()
    jugadores = df_pr['id_jugador'].unique()
    for jug in jugadores:
        for cat in categorias:
            prono = df_pr[(df_pr['categoria'] == cat) & (df_pr['id_jugador'] == jug)]['prediccion_jugador'].values
            prono = [p.strip().lower() for p in prono if isinstance(p, str) and p.strip() != '']
            ganador_real = df_pr[(df_pr['categoria'] == cat)]['ganador_real'].dropna().unique()
            ganador_real = [g.strip().lower() for g in ganador_real if isinstance(g, str) and g.strip() != '']
            puntos = 0
            if len(prono) > 0 and len(ganador_real) > 0:
                aciertos = 0
                if cat in ['16vos', '8vo']:
                    for p in prono:
                        if p in ganador_real:
                            puntos += puntos_por_categoria.get(cat, 0)
                            aciertos += 1
                if cat in ['4tos', 'Semis', 'Final', 'Tercer Lugar', 'Campeón', 'Goleador']:
                    if set(prono) == set(ganador_real):
                        puntos = puntos_por_categoria.get(cat, 0)
                        aciertos = "Acierto total"
            list_df_pr.append({'id_jugador': jug, 'categoria': cat, 'aciertos': aciertos, 'puntos_premios': puntos})
    
    df_pr = pd.DataFrame(list_df_pr)
    #pts_premios = df_pr.groupby(['id_jugador'])['puntos_premios'].sum().reset_index()
    pts_premios = df_pr.groupby('id_jugador')['puntos_premios'].sum().reset_index()

    # ---------------------------------------------------------
    # 3. TABLA DE POSICIONES FINAL (CONSOLIDADO)
    # ---------------------------------------------------------
    
    # Cruzamos todo con los nombres reales de los jugadores
    df_final = pd.merge(df_jugadores, pts_partidos, on='id_jugador', how='left')
    df_final = pd.merge(df_final, pts_premios, on='id_jugador', how='left')

    # Limpiamos valores nulos (jugadores sin puntos aún)
    df_final['puntos_partidos'] = df_final['puntos_partidos'].fillna(0).astype(int)
    df_final['puntos_premios'] = df_final['puntos_premios'].fillna(0).astype(int)
    
    # El puntaje sagrado
    df_final['PUNTAJE_TOTAL'] = df_final['puntos_partidos'] + df_final['puntos_premios']
    
    # Ordenamos del Campeón al Último Lugar
    df_final = df_final.sort_values(by='PUNTAJE_TOTAL', ascending=False).reset_index(drop=True)
    
    # Ajustamos la vista final
    df_final.index = df_final.index + 1 # Para que el ranking empiece en 1 y no en 0
    tabla_clasificacion = df_final[['nombre_jugador', 'PUNTAJE_TOTAL', 'puntos_partidos', 'puntos_premios']]
    tabla_clasificacion.columns = ['Jugador', 'Puntos Totales', 'Pts Partidos', 'Pts Fases']
    
    return tabla_clasificacion, df_p, df_pr

# --- FUNCIONES DE ESTILO PARA LA TABLA DE POSICIONES ---
def aplicar_estilos_quiniela(df):
    # Creamos una copia vacía del DataFrame para llenarla con reglas CSS
    df_estilos = pd.DataFrame('', index=df.index, columns=df.columns)
    total_filas = len(df)
    
    # 'RdYlGn_r' es un mapa de colores que va de Verde (Red-Yellow-Green en reversa) a Rojo
    cmap = plt.get_cmap('RdYlGn_r') 
    
    for i in range(total_filas):
        if i == total_filas - 1:
            # ÚLTIMO LUGAR: Fondo negro, letras negras (Castigo de invisibilidad)
            css = 'background-color: black; color: black;'
        elif i == total_filas - 2:
            # PENÚLTIMO LUGAR: Fondo negro, letras blancas
            css = 'background-color: black; color: white;'
        else:
            # GRADIENTE: Para todos los demás (desde el 1ro hasta el antepenúltimo)
            # Evitamos división por cero si hay menos de 3 jugadores
            rango_gradiente = max(1, total_filas - 3) 
            
            # Normalizamos la posición de 0.0 (Verde) a 1.0 (Rojo)
            valor_normalizado = i / rango_gradiente 
            
            # Extraemos el color en formato HEX
            color_rgba = cmap(valor_normalizado)
            color_hex = mcolors.to_hex(color_rgba)
            
            # Texto oscuro para que contraste bien con el fondo brillante
            css = f'background-color: {color_hex}; color: #111111;'
            
        # Aplicamos la regla CSS a todas las columnas de esta fila
        df_estilos.iloc[i] = css
        
    return df_estilos

#%% Ejecución
with st.spinner('Conectando a la base de datos...'):
    df_premios = cargar_datos(URLS["premios_reales"])
    df_partidos = cargar_datos(URLS["partidos_reales"])
    df_pronos_part = cargar_datos(URLS["pronosticos_partidos"]).drop(columns=['equipo_local', 'equipo_visitante']) # Eliminamos la columna de timestamp si existe
    df_pronos_premios = cargar_datos(URLS["pronosticos_premios"]).drop(columns=['categoria']) # Eliminamos la columna de timestamp si existe
    df_jugadores = cargar_datos(URLS["mapeo_jugadores"])

# Ejecución visual
if not df_partidos.empty and not df_pronos_part.empty and not df_premios.empty and not df_pronos_premios.empty and not df_jugadores.empty:
    st.success("¡Conexión exitosa! 🟢")
    st.write("Jugadores Cargado:", df_jugadores.shape[0], ".")

    st.divider()

    if not df_partidos.empty and not df_pronos_part.empty:
        tabla_posiciones, detalle_partidos, detalle_premios = calcular_posiciones(df_partidos, df_premios, df_pronos_part, df_pronos_premios, df_jugadores)

        # 1. Creamos las 4 pestañas solicitadas
        tab1, tab2, tab3, tab4 = st.tabs([
            "🏆 Clasificación", 
            "🕵️‍♂️ Mi Auditoría", 
            "📊 Fases Eliminatorias", 
            "🥇 Campeón y Goleador"
        ])

        # --- TAB 1: CLASIFICACIÓN ---
        with tab1:
            st.header("Tabla de Posiciones General")
            # Aplicamos la pintura mágica que hicimos antes
            tabla_estilizada = tabla_posiciones.style.apply(aplicar_estilos_quiniela, axis=None)
            # Mostramos la tabla completa sin scroll interno
            st.table(tabla_estilizada)

        # --- TAB 2: AUDITORÍA INDIVIDUAL ---
        with tab2:
            st.header("Rendimiento Individual")
            
            # Creamos un buscador/selector con los nombres de la tabla
            lista_jugadores = tabla_posiciones['Jugador'].tolist()
            jugador_elegido = st.selectbox("Selecciona un participante para auditar sus puntos:", lista_jugadores)
            
            if jugador_elegido:
                # Encontramos el ID interno del jugador para filtrar sus datos
                id_interno = df_jugadores[df_jugadores['nombre_jugador'] == jugador_elegido]['id_jugador'].values[0]
                
                # Filtramos sus predicciones
                mis_partidos = detalle_partidos[detalle_partidos['id_jugador'] == id_interno]
                mis_premios = detalle_premios[detalle_premios['id_jugador'] == id_interno]
                
                # Tarjetas visuales de puntuación (KPIs)
                pts_totales = tabla_posiciones[tabla_posiciones['Jugador'] == jugador_elegido]['Puntos Totales'].values[0]
                pts_part = tabla_posiciones[tabla_posiciones['Jugador'] == jugador_elegido]['Pts Partidos'].values[0]
                pts_prem = tabla_posiciones[tabla_posiciones['Jugador'] == jugador_elegido]['Pts Fases'].values[0]
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Puntos Totales", pts_totales)
                col2.metric("Puntos por Partidos", pts_part)
                col3.metric("Puntos por Fases/Premios", pts_prem)
                
                st.divider()
                
                # Mostramos su historial de partidos
                st.subheader("Desglose de Partidos")
                if not mis_partidos.empty:
                    vista_partidos = mis_partidos[['equipo_local', 'goles_local_real', 'goles_visitante_real', 'equipo_visitante', 'goles_local_pronostico', 'goles_visitante_pronostico', 'puntos_partidos']]
                    vista_partidos.columns = ['Local', 'Goles L (Real)', 'Goles V (Real)', 'Visitante', 'Goles L (Prono)', 'Goles V (Prono)', 'Pts Ganados']
                    vista_partidos[['Goles L (Real)', 'Goles V (Real)', 'Goles L (Prono)', 'Goles V (Prono)']] = vista_partidos[['Goles L (Real)', 'Goles V (Real)', 'Goles L (Prono)', 'Goles V (Prono)']].astype(int)
                    
                    # Resaltamos en verde los partidos donde sumó puntos
                    def resaltar_puntos(val):
                        if val == 3:
                            color = '#c3e6cb' # Verde acierto pleno
                        elif val == 1:
                            color = '#d4edda' # Verde claro si ganó puntos
                        else:
                            color = '' # Sin color si no ganó puntos
                        return f'background-color: {color}'
                    
                    st.dataframe(vista_partidos.style.map(resaltar_puntos, subset=['Pts Ganados']))
                else:
                    st.info("Aún no hay partidos con resultados oficiales evaluados.")
                    
                # Mostramos su historial de premios
                st.subheader("Desglose de Fases y Premios")
                if not mis_premios.empty:
                    vista_premios = mis_premios[['categoria', 'aciertos', 'puntos_premios']]
                    vista_premios.columns = ['Categoría', 'Sus Aciertos', 'Pts Ganados']
                    
                    st.dataframe(vista_premios)
                else:
                    st.info("Aún no se han definido ganadores de fases o premios.")

        # --- TAB 3: PÁGINA DE FASES (NUEVA) ---
        with tab3:
            st.header("Pronósticos de Fases")
            st.write("Seguimiento de quiénes avanzan en cada ronda.")
            
            # Filtramos categorías de fases
            cats_fases = ['16vos', '8vos', '4tos', 'Semis', 'Final', 'Tercer lugar']
            df_fases = pd.merge(df_pronos_premios, df_premios, on='id_premio', how='left')
            df_fases = pd.merge(df_fases, df_jugadores[['id_jugador', 'nombre_jugador']], on='id_jugador', how='left')
            df_fases = df_fases[df_fases['categoria'].isin(cats_fases)]

            # Creamos una vista pivotada: Jugadores en filas, Categorías en columnas
            # Nota: Como hay múltiples cupos por fase, mostramos un resumen por categoría
            for fase in cats_fases:
                with st.expander(f"Ver detalle: {fase}"):
                    ganadores_reales = df_fases[df_fases['categoria'] == fase]['ganador_real'].dropna().unique()
                    fase_pivot = df_fases[df_fases['categoria'] == fase].pivot(
                        index='nombre_jugador', columns='id_premio', values='prediccion_jugador'
                    )
                    fase_pivot.columns = [f"{fase} - Cupo {i+1}" for i in range(fase_pivot.shape[1])]
                    
                    df_fases_fase = df_fases[df_fases['categoria'] == fase]
                    df_fases_fase['puntos_premios'] = df_fases_fase['prediccion_jugador'].apply(lambda x: 1 if x in ganadores_reales else 0)
                    
                    # Obtenemos los puntos para colorear (misma estructura que el pivot)
                    fase_puntos = df_fases_fase.pivot(
                        index='nombre_jugador', columns='id_premio', values='puntos_premios'
                    )
                    fase_puntos.columns = [f"{fase} - Cupo {i+1}" for i in range(fase_puntos.shape[1])]

                    # Función para pintar celdas basado en acierto/fallo
                    def colorear_fases(val_puntos):
                        # Si no hay predicción, no pintamos
                        if pd.isna(val_puntos) or val_puntos == "" or val_puntos == "nan": return ''
                        
                        if val_puntos > 0:
                            return 'background-color: #c3e6cb; color: #155724;' # Verde acierto
                        else:
                            return 'background-color: #f5c6cb; color: #721c24;' # Rojo fallo
                        return '' # Pendiente
                    
                    # Aplicamos el estilo
                    def aplicar_color_fase(df_data):
                        color_df = pd.DataFrame('', index=df_data.index, columns=df_data.columns)
                        for col in df_data.columns:
                            for idx in df_data.index:
                                try:
                                    pts = fase_puntos.loc[idx, col]
                                    color_df.loc[idx, col] = colorear_fases(pts)
                                except: pass
                        return color_df

                    st.dataframe(fase_pivot.style.apply(aplicar_color_fase, axis=None))

        # --- TAB 4: CAMPEÓN Y GOLEADOR (NUEVA) ---
        with tab4:
            st.header("Cuadro de Campeón y Goleador")

            df_tops = pd.merge(df_pronos_premios, df_premios, on='id_premio', how='left')
            df_tops = pd.merge(df_tops, df_jugadores[['id_jugador', 'nombre_jugador']], on='id_jugador', how='left')
            df_tops = df_tops[df_tops['categoria'].isin(['Campeón', 'Goleador'])]
            df_tops['puntos_premios'] = df_tops['prediccion_jugador'] == df_tops['ganador_real']
            df_tops['puntos_premios'] = df_tops['puntos_premios'].astype(int)

            top_pivot = df_tops.pivot(index='nombre_jugador', columns='categoria', values='prediccion_jugador')

            # Lógica de color simplificada para esta tabla
            def colorear_tops(col):
                # Obtenemos la categoría (nombre de la columna)
                cat_name = col.name
                styles = []
                for jugador_alias, prono in col.items():
                    id_jug = df_jugadores[df_jugadores['nombre_jugador'] == jugador_alias]['id_jugador'].values[0]
                    pts = df_tops[(df_tops['id_jugador'] == id_jug) & (df_tops['categoria'] == cat_name)]['puntos_premios'].values[0]
                    styles.append(colorear_fases(pts))
                return styles

            st.table(top_pivot.style.apply(colorear_tops))

else:
    st.error("⚠️ Esperando URLs válidas. Por favor actualiza el diccionario 'URLS' en el código.")