#include <stdio.h>
#include <stdlib.h>
#include <time.h>
typedef int data;
struct nodo
{
	data el;
	struct nodo *next;
};
typedef struct nodo *lista;

int lunghezza (lista l);
lista ricerca (lista l, data el);
lista inserisci_testa (lista l, data el);
lista inserisci_coda (lista l, data el);
lista rimuovi_testa (lista l);
lista rimuovi_coda (lista l);
lista rimuovi(lista l, data el);
void stampa (lista l);

int lunghezzaIter (lista l);
lista ricercaIter (lista l, data el);

lista inserisci_codaIter (lista l, data el);
lista rimuovi_testaIter (lista l);
lista rimuovi_codaIter (lista l);
lista rimuoviIter(lista l, data el);
void stampaIter (lista l);
