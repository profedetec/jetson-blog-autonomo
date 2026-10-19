"""
SalonDeTec Publisher - Publica artículos en el blog
"""

import re
import os
import requests
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urljoin

class SalonDeTecPublisher:
    """Publica artículos en salondetec.com"""
    
    def __init__(self, config: Dict):
        self.blog_url = config['blog_url']
        self.admin_url = config['admin_url']
        self.login_url = config['login_url']
        self.credentials = config['credentials']
        self.session = requests.Session()
        
        # Headers para simular navegador
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
        })
    
    def publish(self, blog_post: Dict) -> bool:
        """
        Publica un artículo en el blog.
        
        Args:
            blog_post: Dict con title, excerpt, body, tags, image_path
            
        Returns:
            True si se publicó correctamente
        """
        try:
            # 1. Hacer login
            print("1. Iniciando sesión...")
            if not self._login():
                print("Error: No se pudo iniciar sesión")
                return False
            
            # 2. Extraer token CSRF
            print("2. Obteniendo token CSRF...")
            csrf_token = self._get_csrf_token()
            if not csrf_token:
                print("Error: No se pudo obtener token CSRF")
                return False
            
            # 3. Preparar datos del artículo
            print("3. Preparando artículo...")
            form_data = self._prepare_form_data(blog_post, csrf_token)
            
            # 4. Subir imagen si existe
            files = None
            if blog_post.get('image_path'):
                print("4. Subiendo imagen...")
                files = self._prepare_image(blog_post['image_path'])
            
            # 5. Enviar formulario
            print("5. Publicando artículo...")
            success = self._submit_article(form_data, files)
            
            return success
            
        except Exception as e:
            print(f"Error durante la publicación: {e}")
            return False
    
    def _login(self) -> bool:
        """
        Realiza el login en el panel de administración.

        La verificación es por acceso efectivo a una página protegida, no por
        la presencia de la cookie de sesión: el servidor emite 'salondetec_sso'
        también a visitantes anónimos, así que usarla como prueba de login
        daba falsos positivos y convertía un fallo de credenciales en un
        confuso "no se encontró token CSRF" más adelante.

        El aviso de error se busca por el elemento renderizado
        ('class="acceso__error"'), no por el nombre de la clase a secas: el
        rediseño del login incrustó el CSS en la propia página, así que
        '.acceso__error' aparece siempre y daba por rechazada toda sesión.
        """
        try:
            # Primero obtener la página de login (fija cookies iniciales).
            # El host puede redirigir (www → dominio raíz) y un 301 convierte
            # el POST en GET: las credenciales se perderían por el camino. Se
            # envía el formulario a la URL ya resuelta.
            inicial = self.session.get(self.login_url, allow_redirects=True)
            login_url = inicial.url or self.login_url

            # Enviar credenciales
            response = self.session.post(
                login_url,
                data=self.credentials,
                allow_redirects=True
            )

            # El sitio reexpone el formulario con un aviso cuando falla
            if ('class="acceso__error"' in response.text
                    or 'incorrectos' in response.text):
                print("Login fallido: el sitio rechazó usuario o contraseña")
                return False

            # Prueba real: pedir una página protegida y ver si nos deja entrar
            if self._sesion_activa():
                print("Login exitoso")
                return True

            print("Login fallido: la sesión no quedó autenticada "
                  f"(se redirige a {self.login_url})")
            return False

        except Exception as e:
            print(f"Error durante login: {e}")
            return False

    def _sesion_activa(self) -> bool:
        """True si la sesión puede abrir el editor sin rebotar al login."""
        try:
            r = self.session.get(f"{self.admin_url}/post-edit.php",
                                 allow_redirects=True)
            return r.status_code == 200 and 'login.php' not in r.url
        except Exception:
            return False
    
    def _get_csrf_token(self) -> Optional[str]:
        """Extrae el token CSRF de la página de edición"""
        try:
            edit_url = f"{self.admin_url}/post-edit.php"
            response = self.session.get(edit_url)
            
            # Buscar token CSRF
            csrf_match = re.search(
                r'<input\s+type="hidden"\s+name="csrf"\s+value="([^"]+)"',
                response.text
            )
            
            if csrf_match:
                return csrf_match.group(1)
            
            # Patrón alternativo
            csrf_match = re.search(r'name="csrf"\s+value="([^"]+)"', response.text)
            if csrf_match:
                return csrf_match.group(1)
            
            print("No se encontró token CSRF")
            return None
            
        except Exception as e:
            print(f"Error al obtener CSRF: {e}")
            return None
    
    def _prepare_form_data(self, blog_post: Dict, csrf_token: str) -> Dict:
        """Prepara los datos del formulario"""
        
        # Limpiar y preparar el contenido HTML
        body_html = blog_post.get('body', '')
        
        # Convertir tags a string si es lista
        tags = blog_post.get('tags', [])
        if isinstance(tags, list):
            tags = ', '.join(tags)
        
        form_data = {
            'csrf': csrf_token,
            'title': blog_post.get('title', '')[:200],  # Max 200 chars
            'excerpt': blog_post.get('excerpt', '')[:300],  # Max 300 chars
            'body': body_html,
            'tags': tags[:300],  # Max 300 chars
            'published': '1'  # Publicar inmediatamente
        }
        
        return form_data
    
    def _prepare_image(self, image_path: str) -> Optional[Dict]:
        """Prepara la imagen para subir"""
        try:
            path = Path(image_path)
            
            if not path.exists():
                print(f"Imagen no encontrada: {image_path}")
                return None
            
            # Determinar content type
            content_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            
            content_type = content_types.get(path.suffix.lower(), 'image/jpeg')
            
            # Abrir y leer archivo
            with open(path, 'rb') as f:
                files = {
                    'image': (path.name, f, content_type)
                }
                # Necesitamos mantener el archivo abierto
                # Retornamos los datos para ser usados después
                return {
                    'filename': path.name,
                    'content': f.read(),
                    'content_type': content_type
                }
                
        except Exception as e:
            print(f"Error al preparar imagen: {e}")
            return None
    
    def _submit_article(self, form_data: Dict, image_data: Optional[Dict]) -> bool:
        """Envía el formulario de artículo"""
        try:
            edit_url = f"{self.admin_url}/post-edit.php"
            
            if image_data:
                # Con imagen - usar multipart
                files = {
                    'image': (
                        image_data['filename'],
                        image_data['content'],
                        image_data['content_type']
                    )
                }
                
                response = self.session.post(
                    edit_url,
                    data=form_data,
                    files=files,
                    allow_redirects=True
                )
            else:
                # Sin imagen
                response = self.session.post(
                    edit_url,
                    data=form_data,
                    allow_redirects=True
                )
            
            # Verificar éxito
            if response.status_code == 200:
                # Buscar mensaje de éxito
                if 'artículo' in response.text.lower() or 'publicado' in response.text.lower():
                    print("Artículo publicado exitosamente")
                    return True
                
                # Verificar si no hay errores
                if 'error' not in response.text.lower():
                    print("Artículo probablemente publicado")
                    return True
            
            print(f"Respuesta inesperada: {response.status_code}")
            return False
            
        except Exception as e:
            print(f"Error al enviar artículo: {e}")
            return False
    
    def verify_publication(self, article_title: str) -> bool:
        """Verifica que el artículo fue publicado"""
        try:
            response = self.session.get(f"{self.blog_url}/")
            return article_title.lower() in response.text.lower()
        except:
            return False

# Función de prueba
if __name__ == "__main__":
    config = {
        "blog_url": "https://example.com/blog",
        "admin_url": "https://example.com/blog/admin",
        "login_url": "https://example.com/admin/login.php",
        "credentials": {
            "rol": os.environ.get("BLOG_USER", ""),
            "pass": os.environ.get("BLOG_PASS", "")
        }
    }
    
    publisher = SalonDeTecPublisher(config)
    print("Publisher inicializado correctamente")
    print(f"Blog URL: {config['blog_url']}")
