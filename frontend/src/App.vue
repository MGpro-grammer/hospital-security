<script>
import { login, handleRedirect } from '@/services/auth.js'
import { enroll, restorePrivateKey } from '@/services/enrollment.js'

export default {
  name: 'App',

  data() {
    return {
      journal: '',
      utilisateur: null,
    }
  },

  async mounted() {
    try {
      const claims = await handleRedirect()
      if (claims) {
        this.utilisateur = claims.preferred_username
        this.log(`Connecte : ${claims.preferred_username}`)
        this.log(`Groupes  : ${(claims.groups || []).join(', ') || 'aucun'}`)
        this.log('')
      }
    } catch (e) {
      this.log(`ERREUR connexion : ${e.message}`)
    }
  },

  methods: {
    /** @param {string} message */
    log(message) {
      this.journal += message + '\n'
    },

    seConnecter() {
      login()
    },

    async enregistrerCles() {
      try {
        this.log('Derivation de la cle et generation de la paire RSA...')
        const { publicKey } = await enroll()
        this.log('Cles enregistrees sur le serveur.')
        this.log(`Cle publique (debut) : ${publicKey.slice(0, 60)}...`)
        this.log('')
      } catch (e) {
        this.log(`ERREUR : ${e.message}`)
        this.log('')
      }
    },

    async restaurerCle() {
      try {
        this.log('Recuperation et dechiffrement de la cle privee...')
        const privateKey = await restorePrivateKey()
        this.log(`Cle privee restauree : ${privateKey.algorithm.name}, ` +
            `${privateKey.algorithm.modulusLength} bits`)
        this.log(`Extractible : ${privateKey.extractable} (false = ne peut pas etre lue)`)
        this.log('')
      } catch (e) {
        this.log(`ERREUR : ${e.message}`)
        this.log('')
      }
    },
  },
}
</script>

<template>
  <main>
    <h1>Hospital Security</h1>
    <p v-if="utilisateur">Utilisateur : <strong>{{ utilisateur }}</strong></p>
    <p v-else>Non connecte.</p>

    <button @click="seConnecter" :disabled="!!utilisateur">1. Se connecter</button>
    <button @click="enregistrerCles" :disabled="!utilisateur">2. Enregistrer mes cles</button>
    <button @click="restaurerCle" :disabled="!utilisateur">3. Restaurer ma cle privee</button>
    <button @click="journal = ''">Effacer</button>

    <pre>{{ journal }}</pre>
  </main>
</template>

<style scoped>
main { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
button { padding: .6rem 1rem; margin: .3rem .3rem .3rem 0; font-size: 1rem; cursor: pointer; }
pre { background: #f4f4f4; padding: 1rem; white-space: pre-wrap; word-break: break-all; }
</style>