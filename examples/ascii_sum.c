#include <stdio.h>
#include <string.h>

int main()
{
	int sum = 0;
	char input[10];
	scanf("%9s", input);
	for (int i = 0; i < strlen(input); ++i)
	{
		sum += input[i];
	}
	printf("%d\n", sum);
	return 0;
}
