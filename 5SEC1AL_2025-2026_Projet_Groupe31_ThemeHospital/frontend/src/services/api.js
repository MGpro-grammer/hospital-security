/**
 * @file Client HTTP de l'API, ajoutant le jeton porteur a chaque requete.
 */

import { API_BASE_URL } from '@/config.js'
import { getToken } from './auth.js'

/**
 * Construit un message lisible a partir d'une reponse d'erreur.
 *
 * DRF renvoie deux formes :
 *   {"detail": "Profil deja cree."}              -- erreur globale
 *   {"organisation": ["This field is required."]} -- erreur par champ
 *
 * Le code d'origine ne lisait que `detail` et affichait un opaque
 * "Erreur HTTP 400" dans le second cas.
 *
 * On n'affiche QUE des messages produits par la validation applicative,
 * jamais une trace technique -- avec DEBUG=False le serveur n'en envoie
 * de toute facon aucune, et c'est bien ainsi : un message d'erreur
 * bavard renseigne autant l'attaquant que l'utilisateur.
 *
 * @param {object} body
 * @param {number} statut
 * @returns {string}
 */
function messageErreur(body, statut) {
    if (typeof body.detail === 'string') return body.detail

    const champs = Object.entries(body)
        .filter(([, valeur]) => Array.isArray(valeur))
        .map(([champ, messages]) => `${champ} : ${messages.join(' ')}`)

    return champs.length ? champs.join(' | ') : `Erreur HTTP ${statut}`
}

/**
 * @param {string} path Chemin relatif, ex. "/users/keys/me".
 * @param {object} [options] Options fetch supplementaires.
 * @returns {Promise<object>} Le corps JSON de la reponse.
 * @throws {Error} Si la reponse n'est pas un succes HTTP.
 */
async function request(path, options = {}) {
    const token = getToken()
    if (!token) throw new Error('Non authentifie.')

    const response = await fetch(API_BASE_URL + path, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            ...(options.headers || {}),
        },
    })

    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
        throw new Error(messageErreur(body, response.status))
    }
    return body
}

/** @param {string} path @returns {Promise<object>} */
export function apiGet(path) {
    return request(path)
}

/** @param {string} path @param {object} data @returns {Promise<object>} */
export function apiPost(path, data) {
    return request(path, { method: 'POST', body: JSON.stringify(data) })
}

/**
 * @param {string} path
 * @param {object} [data] Corps optionnel. Une suppression de fichier doit
 *        transporter le nouveau manifeste signe : retirer un fichier du
 *        dossier, c'est modifier la liste qui fait foi.
 * @returns {Promise<object>}
 */
export function apiDelete(path, data) {
    return request(path, {
        method: 'DELETE',
        ...(data ? { body: JSON.stringify(data) } : {}),
    })
}