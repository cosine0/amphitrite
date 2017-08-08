#include <stdio.h>

char rotate_char(char c, int amount)
{
	return 'a' + (c -'a' + amount) % 26;	
}

int main()
{
	char message[256];
	puts("You have to decrypt this text: ");
	puts("wulbtvuvbsayhtpjyvzjvwpjzpspjvcvsjhuvjvupvzpz");
	
	printf("input message to encrypt in lowercase> ");
	scanf("%255s", message);

	int i;
	for (i = 0; message[i]; i++)
		message[i] = rotate_char(message[i], 7);

	printf("encrypted: %s\n", message);
	return 0;
}
