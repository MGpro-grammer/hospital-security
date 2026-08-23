/**
 * @file Configuration publique du client.
 *
 * Ces valeurs ne sont PAS des secrets : elles sont par nature visibles dans
 * le code telecharge par le navigateur. Les regrouper ici evite de les
 * disperser dans le code.
 */

export const KEYCLOAK_REALM_URL = 'https://localhost:8443/realms/hospital'
export const KEYCLOAK_CLIENT_ID = 'hospital-frontend'
export const API_BASE_URL = 'https://localhost:8000/api'