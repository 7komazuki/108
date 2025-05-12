import random
import json

class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.lives = 2
        self.score = 0
        self.passed = False
        self.cleared = False
        
    def lose_life(self):
        self.lives -= 1
        return f"{self.name} loses one life"
        
    def score_one(self):
        self.score += 1
        return f"{self.name} earns one point"
        
class NanatoridoriGame:
    def __init__(self, player_names):
        self.player_names = player_names  # List of player names in session
        self.players = {name: Player(name) for name in player_names}
        self.active_players = player_names.copy()  # Players currently connected
        self.deck = [i for i in range(1, 8)] * 9  # Cards 1-7, 9 copies each
        self.current_player_index = 0
        self.current_player_name = player_names[0] if player_names else ""
        self.table = []
        self.game_over = False
        self.number_of_wins = 0
        self.passes_combo = 0
        self.last_played_by = None
        self.message_log = []
        self.discard_pile = []
        self.winner = None
        # Shuffle deck after message_log is initialized
        self.shuffle_deck()
        
    def shuffle_deck(self):
        random.shuffle(self.deck)
        self.log_message("Deck shuffled")
        
    def deal_cards(self):
        for player_name in self.player_names:
            for _ in range(8):
                self.players[player_name].hand.append(self.deck.pop())
        self.log_message("Cards dealt to all players")
        
    def new_round(self):
        # Reset player status
        for name in self.player_names:
            player = self.players[name]
            player.cleared = False
            player.hand.clear()
            player.passed = False

        self.number_of_wins = 0
        self.passes_combo = 0

        # Make sure game is not over and winner is reset
        self.game_over = False
        self.winner = None
        self.last_played_by = None

        # Only retain players who are marked as active
        # This removes disconnected players from the display

        # Reset and shuffle the deck
        self.deck = [i for i in range(1, 8)] * 9
        self.shuffle_deck()

        # Only deal cards if there are players
        if self.player_names:
            self.deal_cards()

        # Clear the table and discard pile
        self.table.clear()
        self.discard_pile = []
        self.log_message("New round started")

        # Reset the current player to the first player
        if self.player_names:
            self.current_player_index = 0
            self.current_player_name = self.player_names[0]
        
    def insert_card(self, player_name, new_cards, position):
        """Add cards to a player's hand at the specified position"""
        player = self.players[player_name]
        
        # Validate position
        if position < 0:
            position = 0
        elif position > len(player.hand):
            position = len(player.hand)
            
        # Insert cards at position
        for i, card in enumerate(new_cards):
            player.hand.insert(position + i, card)
            
        self.log_message(f"{player_name} added {len(new_cards)} card(s) to their hand")
        return True

    def play_card(self, player_name, card_indices):
        """Play cards from a player's hand"""
        player = self.players[player_name]
        
        # Ensure it's this player's turn
        if player_name != self.current_player_name:
            self.log_message(f"Not {player_name}'s turn")
            return False, "Not your turn"
            
        # Get the actual card values
        if not card_indices or len(card_indices) == 0:
            return False, "No cards selected"
            
        # Validate indices
        for idx in card_indices:
            if idx < 0 or idx >= len(player.hand):
                return False, "Invalid card index"
        
        # Get the selected cards
        selected_cards = [player.hand[idx] for idx in card_indices]
        
        # Check if all selected cards have the same value
        if len(set(selected_cards)) != 1:
            return False, "All selected cards must have the same value"
            
        # Check if the cards are adjacent
        sorted_indices = sorted(card_indices)
        for i in range(len(sorted_indices) - 1):
            if sorted_indices[i + 1] - sorted_indices[i] != 1:
                return False, "Selected cards must be adjacent"
                
        # Check if the play is valid according to game rules
        if len(self.table) > 0:
            # Table has cards, need to check if this play beats them
            if (len(selected_cards) > len(self.table)) or \
               (len(selected_cards) == len(self.table) and selected_cards[0] > self.table[0]):
                # Valid play
                pass
            else:
                return False, "Play must have more cards or higher value than current table"
        
        # Play is valid, remove cards from hand
        # Remove from highest index to lowest to avoid shifting issues
        cards_to_play = selected_cards.copy()
        for idx in sorted(card_indices, reverse=True):
            player.hand.pop(idx)
            
        # Update table
        old_table = self.table.copy()
        self.table = cards_to_play
        self.last_played_by = player_name
        
        # Reset passes combo
        self.passes_combo = 0
        
        self.log_message(f"{player_name} played {len(cards_to_play)} card(s) of value {cards_to_play[0]}")
        
        # Move to next player
        self.advance_turn()
        
        # Check if player has emptied their hand
        if len(player.hand) == 0:
            player.cleared = True
            message = player.score_one()
            self.log_message(message)
            self.number_of_wins += 1
            
            # If everyone but one player has won, that player loses
            if self.number_of_wins == len(self.player_names) - 1:
                # Find the player who hasn't cleared
                for name, p in self.players.items():
                    if not p.cleared:
                        message = p.lose_life()
                        self.log_message(message)
                        self.log_message(f"{name} has {p.lives} lives remaining")
                        
                        # Check if the game is over
                        if p.lives <= 0:
                            self.game_over = True
                            self.log_message(f"Game over! {name} has lost all lives.")
                        else:
                            # Start a new round
                            self.new_round()
                        break
        
        return True, old_table
        
    def pass_turn(self, player_name):
        """Player passes their turn and draws a card"""
        player = self.players[player_name]
        
        # Ensure it's this player's turn
        if player_name != self.current_player_name:
            self.log_message(f"Not {player_name}'s turn")
            return False, "Not your turn"
            
        # Draw a card from the deck
        if len(self.deck) > 0:
            new_card = self.deck.pop()
            self.log_message(f"{player_name} passes and draws a card ({new_card})")
            
            # Add card to the player's hand
            player.hand.append(new_card)
            
            # Mark player as passed
            player.passed = True
            
            # Increase passes combo
            self.passes_combo += 1
            
            # Check if everyone has passed
            active_players = len([p for name, p in self.players.items() if not p.cleared])
            if self.passes_combo >= active_players:
                # Everyone has passed, clear the table
                self.table = []
                self.last_played_by = None
                self.passes_combo = 0
                self.log_message("Everyone passed. Table cleared.")
            
            # Move to next player
            self.advance_turn()
            return True, new_card
        else:
            self.log_message("Deck is empty!")
            return False, "Deck is empty"
            
    def take_cards(self, player_name):
        """Take cards from the table"""
        if player_name != self.current_player_name:
            return False, "Not your turn"
            
        if len(self.table) == 0 or self.last_played_by == player_name:
            return False, "No cards to take or you played these cards"
            
        # Add table cards to player's hand
        taken_cards = self.table.copy()
        player = self.players[player_name]
        player.hand.extend(taken_cards)
        
        self.log_message(f"{player_name} takes {len(taken_cards)} card(s) from the table")
        
        # Clear the table
        self.table = []
        self.last_played_by = None
        
        return True, taken_cards
        
    def discard_cards(self, player_name):
        """Discard cards from the table without taking them"""
        if player_name != self.current_player_name:
            return False, "Not your turn"
            
        if len(self.table) == 0 or self.last_played_by == player_name:
            return False, "No cards to discard or you played these cards"
            
        # Move table cards to discard pile
        discarded = self.table.copy()
        self.discard_pile.extend(discarded)
        
        self.log_message(f"{player_name} discards {len(discarded)} card(s)")
        
        # Clear the table
        self.table = []
        self.last_played_by = None
        
        return True, None
        
    def advance_turn(self):
        """Move to the next player's turn"""
        # If no players, return empty string
        if not self.player_names:
            return ""

        # Find next active player
        start_idx = self.current_player_index

        try:
            while True:
                self.current_player_index = (self.current_player_index + 1) % len(self.player_names)
                next_player_name = self.player_names[self.current_player_index]
                next_player = self.players[next_player_name]

                # Skip players who have cleared their hand
                if not next_player.cleared:
                    break

                # If we've checked all players and come back to the start, break to avoid infinite loop
                if self.current_player_index == start_idx:
                    break

            self.current_player_name = self.player_names[self.current_player_index]
        except (IndexError, ZeroDivisionError) as e:
            # If there's an error, log it and reset to safe values
            print(f"Error in advance_turn: {e}")
            self.current_player_index = 0
            self.current_player_name = self.player_names[0] if self.player_names else ""

        return self.current_player_name
        
    def get_game_state(self):
        """Return the current game state for the frontend"""
        # Create a state object that matches the expected format in game.html
        hands = {}
        lives = {}
        scores = {}

        # Only include active players in the game state
        for name, player in self.players.items():
            # Include the player if they're active or this is the current player's hand
            if name in self.active_players:
                hands[name] = player.hand.copy()
                lives[name] = player.lives
                scores[name] = player.score

        state = {
            "hands": hands,
            "lives": lives,
            "scores": scores,
            "current_player": self.current_player_name,
            "deck_count": len(self.deck),
            "discard_count": len(self.discard_pile),
            "game_over": self.game_over,
            "winner": self.winner,
            "message_log": self.message_log[-10:] if self.message_log else [],
            "table": self.table.copy() if self.table else []
        }

        # Add current play information if there are cards on the table
        if self.table:
            state["current_play"] = {
                "cards": self.table,
                "player": self.last_played_by if self.last_played_by else "Unknown"
            }
            
        return state
        
    def log_message(self, message):
        """Add a message to the game log"""
        self.message_log.append(message)

    def mark_player_active(self, player_name):
        """Mark a player as active/connected"""
        if player_name in self.player_names and player_name not in self.active_players:
            self.active_players.append(player_name)
            self.log_message(f"{player_name} is now active")
            return True
        return False

    def mark_player_inactive(self, player_name):
        """Mark a player as inactive/disconnected"""
        if player_name in self.active_players:
            self.active_players.remove(player_name)
            self.log_message(f"{player_name} is now inactive")

            # If it was this player's turn, advance to the next player
            if player_name == self.current_player_name:
                self.advance_turn()

            return True
        return False

    def admin_force_win(self, player_name):
        """Force a player to win the game (admin function)"""
        if player_name not in self.players:
            return False, f"Player {player_name} not found"

        # Set player as winner
        self.winner = player_name
        self.game_over = True
        self.log_message(f"[ADMIN] {player_name} has been declared the winner!")

        # Make sure the player has at least one score point
        self.players[player_name].score += 1

        # Give all other players 0 lives
        for name, player in self.players.items():
            if name != player_name:
                player.lives = 0

        return True, f"{player_name} wins by admin decision"

    def admin_force_loss(self, player_name):
        """Force a player to lose the game (admin function)"""
        if player_name not in self.players:
            return False, f"Player {player_name} not found"

        # Set player lives to 0
        self.players[player_name].lives = 0

        # Log the action
        self.log_message(f"[ADMIN] {player_name} has been eliminated!")

        # Check if only one player remains with lives
        remaining_players = [name for name, player in self.players.items() if player.lives > 0]

        if len(remaining_players) == 1:
            # Set the last remaining player as winner
            self.winner = remaining_players[0]
            self.game_over = True
            self.log_message(f"{remaining_players[0]} wins!")
        elif len(remaining_players) == 0:
            # Everyone has lost
            self.game_over = True
            self.log_message("Game over! All players have been eliminated.")

        return True, f"{player_name} eliminated by admin decision"

# Helper function to convert the game state to JSON
def game_state_to_json(game):
    return json.dumps(game.get_game_state())
    
# Create a game instance from session data
def load_game(session_data, player_names):
    if not session_data or "game_state" not in session_data:
        # Create a new game
        return NanatoridoriGame(player_names)
        
    # Otherwise could implement loading a saved game here
    return NanatoridoriGame(player_names)