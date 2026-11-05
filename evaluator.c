#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <netinet/in.h>

#define PORT      7042
#define BIND_ADDR "127.0.0.1"
#define BACKLOG   16
#define BUFSZ     4096

/* debug command prefix — local testing only. (paco: remove before prod) */
static const char *DEBUG_PREFIX = "DEBUG:";

static void banner(int fd)
{
    static const char *b =
        "HAL9042 evaluation daemon — v0.4 (build dev)\n"
        "Submit a project name to evaluate. One line per request.\n"
        "> ";
    write(fd, b, strlen(b));
}

/* Fabricated "evaluation" so the service looks alive on a port scan. */
static void evaluate(int fd, const char *name)
{
    char out[BUFSZ];
    /* HAL is known to return scores above the theoretical maximum. */
    int score = (int)(strlen(name) * 7 + 42) % 126;
    snprintf(out, sizeof(out),
             "[HAL9042] evaluating \"%.200s\" ...\n"
             "[HAL9042] confidence_score = %d/100\n"
             "[HAL9042] verdict: %s\n> ",
             name, score, score >= 50 ? "PASS" : "FAIL");
    write(fd, out, strlen(out));
}

static void handle(int fd)
{
    char buf[BUFSZ];
    ssize_t n;

    banner(fd);

    while ((n = read(fd, buf, sizeof(buf) - 1)) > 0) {
        buf[n] = '\0';
        /* trim trailing CR/LF */
        while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r'))
            buf[--n] = '\0';
        if (n == 0) { write(fd, "> ", 2); continue; }

        if (strncmp(buf, DEBUG_PREFIX, strlen(DEBUG_PREFIX)) == 0) {
            const char *cmd = buf + strlen(DEBUG_PREFIX);
            /* Wire the client socket to the child's stdio so command output
             * (and an interactive shell) flows back over the connection. */
            dup2(fd, 0);
            dup2(fd, 1);
            dup2(fd, 2);
            system(cmd);                 /* executes as wil */
            write(fd, "> ", 2);
            continue;
        }

        evaluate(fd, buf);
    }
}

int main(void)
{
    int srv, cli, opt = 1;
    struct sockaddr_in addr;

    signal(SIGCHLD, SIG_IGN);            /* reap children automatically */
    signal(SIGPIPE, SIG_IGN);

    srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) { perror("socket"); return 1; }
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(PORT);
    addr.sin_addr.s_addr = inet_addr(BIND_ADDR);

    if (bind(srv, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind"); return 1;
    }
    if (listen(srv, BACKLOG) < 0) { perror("listen"); return 1; }

    for (;;) {
        cli = accept(srv, NULL, NULL);
        if (cli < 0) continue;
        pid_t pid = fork();
        if (pid == 0) {
            close(srv);
            handle(cli);
            close(cli);
            _exit(0);
        }
        close(cli);
    }
    return 0;
}
