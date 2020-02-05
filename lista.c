#include "lista.h"
lista ricerca (lista l, data el)
{
	if(l==NULL || l->el == el)
	{
		return l;
	}
	else
	{
		return ricerca(l->next, el);
	}
}

lista ricercaIter (lista l, data el)
{
	if(l==NULL || l->el == el)
	{
		return l;
	}
	else
	{
		while(l->next!=NULL)
		{
			if(l->el == el)
				return l;
			else
				l=l->next;
		}
		return NULL;
	}
}

lista inserisci_testa (lista l, data el)
{
	struct nodo* temp = malloc(sizeof(struct nodo));
	temp->el = el;
	temp->next = l;
	return temp;
}
	
lista inserisci_coda (lista l, data el)
{
	if(l==NULL)
		return inserisci_testa(l,el);
	else
	{
		l->next = inserisci_coda(l->next,el);
		return l;
	}
}

lista inserisci_codaIter (lista l, data el) 
{
	if(l==NULL)
		return inserisci_testa(l,el);
	else
	{
		struct nodo* coda = malloc(sizeof(struct nodo));
		coda->el=el;
		coda->next=NULL;
		lista temp=l;
		while(temp->next!=NULL)
		{
			temp=temp->next;
		}
		temp->next=coda;
		return l;
	}	
}

lista rimuovi_testa (lista l)
{
	if(l!=NULL)
	{
		lista temp = l;
		l = l->next;
		free(temp);
	}
	return l;			
}	

lista rimuovi_coda (lista l)
{
	if(l!=NULL)
	{
		if(l->next == NULL)
			return rimuovi_testa(l);
		else
		{
			l->next = rimuovi_coda(l->next);
			return l;
		}
	}
	else 
	return NULL;
}

lista rimuovi_codaIter (lista l) //TODO
{
	if(l!=NULL)
	{
		if(l->next == NULL)
			return rimuovi_testa(l);
		else
		{
			lista temp=l;
			while(temp->next!=NULL)
			{
				temp=temp->next;
			}
			  temp=rimuovi_testa(temp);
			  free(temp);
			  return l;
		}
	}
}

int lunghezza (lista l)
{
	if(l==NULL)
		return 0;
	else
		return 1+lunghezza(l->next);
}

int lunghezzaIter (lista l)
{
	int conta=0;
	if(l==NULL)
		return 0;
	else
		while(l->next!=NULL)
		{
			conta++;
			l=l->next;
		}
}
lista rimuovi(lista l, data el)
{
	if(l==NULL)
		return l;
	if(l->el == el)
		return rimuovi_testa(l);
	else
	{
		l->next = rimuovi(l->next,el);
		return l;
	}
}

lista rimuoviIter(lista l, data el)
{
	if(l==NULL)
		return l;
	if(l->el == el)
		return rimuovi_testa(l);
	else
	{
		lista temp=l;
		while(temp->next!=NULL && temp->el !=el )
		{
			temp=temp->next;
		}
		if(temp->next!=NULL)
			return rimuovi_testa(temp->next);
		else
			return l;
	}
}

void stampa(lista l)
{
	if (l==NULL)
        printf("END\n");
    else {
        printf("%d -> ",l->el);
        stampa(l->next);
    }
}

void stampaIter (lista l)
{
	int pos=1;
	if(l!=NULL)
		printf("il valore in posizione 0 = %d\n",l->el);
	while(l->next!=NULL)
	{
		printf("il valore in posizione %d = %d\n",pos,l->next->el);
		l=l->next;
		pos++;
	}
}

