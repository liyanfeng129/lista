#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "lista.h"
int main()
{
   lista l = NULL;
    int i;
    int valore;
 
    srand(time(NULL));
 
    // genero una sequenza casuale di interi
    // che inserisco nella lista tramite la funzione 'inserisci_in_ordine'
    for(i = 0; i < 10; i++) {
        valore = rand() % 100;
        printf("Inserisco: %d\n", valore);
        l = inserisci_codaIter (l, valore); 
    }
       l= rimuovi_codaIter (l);
    
 
    // stampo la lista per verificare che sia effettivamente ordinata
   	stampaIter(l);
 
    return 0;
}
